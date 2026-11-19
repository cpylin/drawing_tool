# -*- coding: utf-8 -*-
"""正交连线路由。

两档策略：

1. **快速路径**：两个锚点在同一水平/垂直线上，或沿该方向无遮挡，直接走直角折线。
2. **网格寻路**：在 ``step`` 粒度的网格上跑 Dijkstra，直行代价低、拐弯加罚、
   斜向代价更高，因此结果天然是"横平竖直、少拐弯"的折线；障碍（方框）内部
   设为不可通行，绕开所有节点。

网格法源自早期 ``flow_lib`` 的实现，这里把参数、缓存与退化情况显式化。
"""
from __future__ import annotations

import heapq
from typing import Iterable, List, Optional, Sequence, Tuple

Point = Tuple[float, float]
Box = Tuple[float, float, float, float]      # left, top, right, bottom

STRAIGHT = 10.0
TURN = 60.0
DIAGONAL = 120.0
#: 穿过一条已经画过的线（垂直相交）的代价。远高于一个网格步长，
#: 让 A* 在长度相近时优先选择不交叉的通道；实测不会拉长常规图的边。
CROSS = 250.0
#: 与已画线同向共用的代价。保持为 0：结构图/树形图共用一条母线是正常画法，
#: 同向重叠不该被当成冲突；只有"垂直穿过"才需要绕。
OVERLAP = 0.0
INF = 1e9


class Router:
    """按绘制区域大小预分配网格的路由器。

    路由器按顺序处理一条图里的所有边，并记住此前每条边占用的网格单元
    （横 / 竖分别记录）。后续边在这些单元上直行或穿过会被加价，于是会主动
    绕开已有连线；这与电路板布线器、Graphviz 的正交边路由是同一思路。
    """

    def __init__(self, width: float, height: float, step: int = 10):
        self.step = step
        self.cols = int(width // step) + 4
        self.rows = int(height // step) + 4
        self.width = width
        self.height = height
        # 已占用单元：横向段 / 纵向段分开，才能区分"平行共用"与"交叉"
        self.h_occ = bytearray(self.cols * self.rows)
        self.v_occ = bytearray(self.cols * self.rows)

    # ------------------------------------------------------------ 占用登记
    def occupy(self, points: Sequence[Point]) -> None:
        """把一条已经完成的折线登记为"已占用"。"""
        if len(points) < 2:
            return
        lengths = [_distance(a, b) for a, b in zip(points, points[1:])]
        total = sum(lengths)
        # 端点附近留出余量：同一节点引出的多条线必须能在锚点附近分开
        guard = self.step * 1.2
        walked = 0.0
        for (a, b), length in zip(zip(points, points[1:]), lengths):
            if length < 1e-6:
                continue
            steps = max(1, int(length / max(1.0, self.step / 2.0)))
            for k in range(steps + 1):
                d = walked + length * k / steps
                if d < guard or total - d < guard:
                    continue
                px = a[0] + (b[0] - a[0]) * k / steps
                py = a[1] + (b[1] - a[1]) * k / steps
                self._mark(px, py, a, b)
            walked += length

    def _mark(self, px: float, py: float, a: Point, b: Point) -> None:
        idx = self._cell(px, py)
        if idx is None:
            return
        horizontal = abs(b[0] - a[0]) >= abs(b[1] - a[1])
        if horizontal:
            self.h_occ[idx] = 1
        else:
            self.v_occ[idx] = 1

    def _cell(self, px: float, py: float):
        cx = int(round(px / self.step))
        cy = int(round(py / self.step))
        if cx < 0 or cy < 0 or cx >= self.cols or cy >= self.rows:
            return None
        return cy * self.cols + cx

    # ------------------------------------------------------------ 入口
    def route(self, start: Point, end: Point, blocked: Sequence[Box],
              sides: Optional[Tuple[str, str]] = None) -> List[Point]:
        if abs(start[0] - end[0]) < 0.5 and abs(start[1] - end[1]) < 0.5:
            return [start, end]

        # 端点所在的两个框不扩容，其余框外扩一圈"安全距离"，
        # 避免 L 形折线贴着别的节点边框走（DFD 里两条标签叠在一起就是这种情况）。
        margin = max(6.0, self.step * 0.7)
        expanded = []
        for box in blocked:
            if _contains(box, start, 2.0) or _contains(box, end, 2.0):
                expanded.append(box)
            else:
                l, t, r, b = box
                expanded.append((l - margin, t - margin, r + margin, b + margin))

        # 共线且无遮挡：一条直线
        if abs(start[1] - end[1]) < 0.5 and self._clear(start, end, expanded):
            if self._occ_cost([start, end]) == 0:
                return [start, end]
        if abs(start[0] - end[0]) < 0.5 and self._clear(start, end, expanded):
            if self._occ_cost([start, end]) == 0:
                return [start, end]

        best = None

        def consider(pts: List[Point]) -> None:
            nonlocal best
            length = sum(_manhattan(a, b) for a, b in zip(pts, pts[1:]))
            score = (self._occ_cost(pts), length)
            if best is None or score < best[0]:
                best = (score, pts)

        # 对向端口优先走 Z 形：中间留一条竖直（或水平）通道，最后垂直进入端口。
        # 这样既不会贴着节点边框走，也给"多条线抢同一条缝"留出不同位置。
        src_side, dst_side = sides if sides else (None, None)
        horizontal_ports = src_side in ("l", "r") and dst_side in ("l", "r")
        vertical_ports = src_side in ("t", "b") and dst_side in ("t", "b")
        if horizontal_ports and abs(start[0] - end[0]) > 1:
            for f in (0.5, 0.4, 0.6, 0.3, 0.7):
                x = start[0] + (end[0] - start[0]) * f
                pts = _simplify([start, (x, start[1]), (x, end[1]), end])
                if all(self._clear(a, b, expanded) for a, b in zip(pts, pts[1:])):
                    consider(pts)
        if vertical_ports and abs(start[1] - end[1]) > 1:
            for f in (0.5, 0.4, 0.6, 0.3, 0.7):
                y = start[1] + (end[1] - start[1]) * f
                pts = _simplify([start, (start[0], y), (end[0], y), end])
                if all(self._clear(a, b, expanded) for a, b in zip(pts, pts[1:])):
                    consider(pts)

        # L 形直角折线（两种拐法）
        for corner in ((end[0], start[1]), (start[0], end[1])):
            if self._clear(start, corner, expanded) and self._clear(corner, end, expanded):
                consider(_simplify([start, corner, end]))
        if best is not None and best[0][0] == 0:
            return best[1]

        grid_path = self._dijkstra(start, end, expanded)
        if len(grid_path) < 2:
            return best[1] if best is not None else [start, end]
        smooth = _simplify(_smooth(grid_path, expanded, self.step))
        if best is not None:
            length = sum(_manhattan(a, b) for a, b in zip(smooth, smooth[1:]))
            if (self._occ_cost(smooth), length) >= best[0]:
                # 网格法没有更好（例如被墙堵住），保留更短的折线
                return best[1]
        return smooth

    # ------------------------------------------------------------ 代价
    def _occ_cost(self, pts: Sequence[Point]) -> float:
        """一条候选折线与已占用通道的冲突代价。"""
        cost = 0.0
        for a, b in zip(pts, pts[1:]):
            horizontal = abs(b[0] - a[0]) >= abs(b[1] - a[1])
            length = _distance(a, b)
            steps = max(1, int(length / max(1.0, self.step / 2.0)))
            for k in range(steps + 1):
                idx = self._cell(a[0] + (b[0] - a[0]) * k / steps,
                                a[1] + (b[1] - a[1]) * k / steps)
                if idx is None:
                    continue
                if horizontal:
                    if self.v_occ[idx]:
                        cost += CROSS
                    elif self.h_occ[idx]:
                        cost += OVERLAP
                else:
                    if self.h_occ[idx]:
                        cost += CROSS
                    elif self.v_occ[idx]:
                        cost += OVERLAP
        return cost

    # ------------------------------------------------------------ 工具
    def _clear(self, a: Point, b: Point, blocked: Sequence[Box]) -> bool:
        """线段（仅轴对齐）是否不穿越任何障碍。"""
        steps = max(1, int(max(abs(b[0] - a[0]), abs(b[1] - a[1])) / self.step))
        for k in range(1, steps):
            px = a[0] + (b[0] - a[0]) * k / steps
            py = a[1] + (b[1] - a[1]) * k / steps
            for l, t, r, bo in blocked:
                if l + 1 < px < r - 1 and t + 1 < py < bo - 1:
                    return False
                # 贴着节点边框走同样算脏线（类图里常见的"双边框"就是这么来的）
                if t - 0.75 <= py <= bo + 0.75 and (abs(px - l) <= 0.75 or abs(px - r) <= 0.75):
                    return False
                if l - 0.75 <= px <= r + 0.75 and (abs(py - t) <= 0.75 or abs(py - bo) <= 0.75):
                    return False
        return True

    def _dijkstra(self, start: Point, end: Point, blocked: Sequence[Box]) -> List[Point]:
        step = self.step
        cols, rows = self.cols, self.rows
        grid = bytearray(cols * rows)
        for (l, t, r, b) in blocked:
            gx0 = max(0, int(l // step) + 1)
            gx1 = min(cols - 1, int(-(-r // step)) - 1)
            gy0 = max(0, int(t // step) + 1)
            gy1 = min(rows - 1, int(-(-b // step)) - 1)
            for gy in range(gy0, gy1 + 1):
                base = gy * cols
                for gx in range(gx0, gx1 + 1):
                    grid[base + gx] = 1

        clamp = lambda v, hi: min(hi, max(0, v))
        sx = clamp(int(round(start[0] / step)), cols - 1)
        sy = clamp(int(round(start[1] / step)), rows - 1)
        ex = clamp(int(round(end[0] / step)), cols - 1)
        ey = clamp(int(round(end[1] / step)), rows - 1)
        si, ei = sy * cols + sx, ey * cols + ex
        grid[si] = 0
        grid[ei] = 0

        dirs = ((0, -1), (0, 1), (-1, 0), (1, 0), (-1, -1), (1, -1), (-1, 1), (1, 1))
        n = cols * rows
        # A* 的 g 与 f 必须分开存：队列里是 f = g + h，比较时不能用 f 去比 g。
        gscore = [INF] * (n * 8)
        fscore = [INF] * (n * 8)
        prev = [-1] * (n * 8)
        start_state = si * 8 + 4
        gscore[start_state] = 0.0
        fscore[start_state] = 0.0
        pq = [(0.0, start_state)]
        best_state, best_cost = -1, INF

        while pq:
            _f, state = heapq.heappop(pq)
            if _f > fscore[state]:
                continue
            idx, pdir = state // 8, state % 8
            if idx == ei:
                if gscore[state] < best_cost:
                    best_state, best_cost = state, gscore[state]
                continue
            cx, cy = idx % cols, idx // cols
            for nd, (dx, dy) in enumerate(dirs):
                nx, ny = cx + dx, cy + dy
                if nx < 0 or ny < 0 or nx >= cols or ny >= rows:
                    continue
                j = ny * cols + nx
                if grid[j]:
                    continue
                c = STRAIGHT if nd < 4 else DIAGONAL
                if nd != pdir:
                    c += TURN
                c += self._move_penalty(j, nd)
                ng = gscore[state] + c
                ns = j * 8 + nd
                if ng + 1e-6 < gscore[ns]:
                    gscore[ns] = ng
                    prev[ns] = state
                    h = 8.0 * max(abs(nx - ex), abs(ny - ey))
                    fscore[ns] = ng + h
                    heapq.heappush(pq, (fscore[ns], ns))

        if best_state < 0:
            return [start, end]

        path: List[Point] = []
        state = best_state
        while state >= 0:
            idx = state // 8
            path.append((idx % cols * step, idx // cols * step))
            state = prev[state]
        path.reverse()
        if not path:
            path = [(sx * step, sy * step)]
        path[0] = (sx * step, sy * step)
        path[-1] = (ex * step, ey * step)
        return [start] + path + [end]

    def _move_penalty(self, idx: int, nd: int) -> float:
        """走进某格时，若与已占用通道相交 / 平行共用，追加代价。"""
        if nd in (0, 1):          # 纵向移动
            if self.h_occ[idx]:
                return CROSS
            return OVERLAP if self.v_occ[idx] else 0.0
        if nd in (2, 3):          # 横向移动
            if self.v_occ[idx]:
                return CROSS
            return OVERLAP if self.h_occ[idx] else 0.0
        return OVERLAP if (self.h_occ[idx] or self.v_occ[idx]) else 0.0


def _distance(a: Point, b: Point) -> float:
    return ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5


def _contains(box: Box, p: Point, tol: float = 0.0) -> bool:
    l, t, r, b = box
    return l - tol <= p[0] <= r + tol and t - tol <= p[1] <= b + tol


def _manhattan(a: Point, b: Point) -> float:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _smooth(points: Sequence[Point], blocked: Sequence[Box], step: int) -> List[Point]:
    """把网格台阶压缩成最少拐点的折线。"""
    if len(points) < 3:
        return list(points)
    out = [points[0]]
    i = 1
    while i < len(points):
        a = out[-1]
        chosen, corner = None, None
        for j in range(len(points) - 1, i - 1, -1):
            b = points[j]
            if abs(a[0] - b[0]) < 0.01 or abs(a[1] - b[1]) < 0.01:
                if _axis_clear(a, b, blocked, step):
                    chosen, corner = b, None
                    break
            else:
                c1 = (b[0], a[1])
                if _axis_clear(a, c1, blocked, step) and _axis_clear(c1, b, blocked, step):
                    chosen, corner = b, c1
                    break
                c2 = (a[0], b[1])
                if _axis_clear(a, c2, blocked, step) and _axis_clear(c2, b, blocked, step):
                    chosen, corner = b, c2
                    break
        if chosen is None:
            out.append(points[i])
            i += 1
        else:
            if corner is not None:
                out.append(corner)
            out.append(chosen)
            try:
                i = points.index(chosen, i) + 1
            except ValueError:
                i = len(points)
    return _simplify(out)


def _axis_clear(a: Point, b: Point, blocked: Sequence[Box], step: int) -> bool:
    steps = max(1, int(max(abs(b[0] - a[0]), abs(b[1] - a[1])) / step))
    for k in range(1, steps):
        px = a[0] + (b[0] - a[0]) * k / steps
        py = a[1] + (b[1] - a[1]) * k / steps
        for l, t, r, bo in blocked:
            if l + 1 < px < r - 1 and t + 1 < py < bo - 1:
                return False
    return True


def _simplify(points: Sequence[Point]) -> List[Point]:
    """去掉重复点与共线中间点。"""
    dedup: List[Point] = []
    for p in points:
        if dedup and abs(p[0] - dedup[-1][0]) < 0.01 and abs(p[1] - dedup[-1][1]) < 0.01:
            continue
        dedup.append((float(p[0]), float(p[1])))
    out: List[Point] = []
    for p in dedup:
        while len(out) >= 2:
            a, b = out[-2], out[-1]
            same_x = abs(a[0] - b[0]) < 0.01 and abs(b[0] - p[0]) < 0.01
            same_y = abs(a[1] - b[1]) < 0.01 and abs(b[1] - p[1]) < 0.01
            if same_x or same_y:
                out.pop()
            else:
                break
        out.append(p)
    return out
