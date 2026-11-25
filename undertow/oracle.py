from collections import deque

import numpy as np

INF = 4095


def bfs_distance(walkable: np.ndarray, exits: np.ndarray, inf: int = INF) -> np.ndarray:
    """Exact multi-source shortest-path distances on the four-neighbour grid."""
    walkable = np.asarray(walkable, dtype=bool)
    exits = np.asarray(exits, dtype=bool) & walkable
    h, w = walkable.shape
    dist = np.full((h, w), inf, dtype=np.int32)
    q = deque()
    for y, x in np.argwhere(exits):
        dist[y, x] = 0
        q.append((int(y), int(x)))
    while q:
        y, x = q.popleft()
        nd = dist[y, x] + 1
        for yy, xx in ((y - 1, x), (y, x + 1), (y + 1, x), (y, x - 1)):
            if 0 <= yy < h and 0 <= xx < w and walkable[yy, xx] and nd < dist[yy, xx]:
                dist[yy, xx] = nd
                q.append((yy, xx))
    return dist


def wrong_cells(field: np.ndarray, oracle: np.ndarray, walkable: np.ndarray) -> np.ndarray:
    return (np.asarray(field) != np.asarray(oracle)) & np.asarray(walkable, dtype=bool)


def exact_match(field: np.ndarray, oracle: np.ndarray, walkable: np.ndarray) -> bool:
    return not bool(wrong_cells(field, oracle, walkable).any())
