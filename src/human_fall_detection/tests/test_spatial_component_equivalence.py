"""Check voxel connectivity against an independent pairwise graph oracle."""
import unittest
import sys
from itertools import product
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.lidar_candidates import spatial_components


def oracle(points, cell_m):
    grid = np.floor(np.asarray(points) / cell_m).astype(int)
    remaining = set(range(len(grid)))
    groups = []
    while remaining:
        seed = min(remaining, key=lambda i: tuple(grid[i]))
        remaining.remove(seed)
        stack, members = [seed], []
        while stack:
            index = stack.pop()
            members.append(index)
            neighbours = [j for j in remaining
                          if np.max(np.abs(grid[index] - grid[j])) <= 1]
            remaining.difference_update(neighbours)
            stack.extend(neighbours)
        groups.append(sorted(members))
    return groups


class SpatialEquivalenceTests(unittest.TestCase):
    def check_points(self, points, cell_m=.05):
        self.assertEqual(spatial_components(points, cell_m), oracle(points, cell_m))

    def test_negative_coordinates_and_digit_boundaries(self):
        self.check_points(np.array([[-5, -5, 9], [-5, -4, 0], [-4, -4, 1],
                                    [9, 9, 0], [9, 8, 9], [-5, -5, 9]]) * .05)

    def test_random_duplicates_and_diagonal_connections(self):
        rng = np.random.RandomState(41)
        for _ in range(20):
            self.check_points(rng.randint(-6, 7, (70, 3)).astype(float) * .05)

    def test_float32_quantization_boundaries(self):
        values = np.array([-.1, -.05, 0, .05, .1], dtype=np.float32)
        values = np.concatenate((values, np.nextafter(values, np.float32(-np.inf)),
                                 np.nextafter(values, np.float32(np.inf))))
        self.check_points(np.column_stack((values, values[::-1], values)))
        points = np.column_stack((values, values[::-1], values))
        expected = [[i * 80 + j for i in group for j in range(80)] for group in oracle(points, .05)]
        self.assertEqual(spatial_components(np.repeat(points, 80, axis=0)), expected)

    def test_block_faces_edges_and_corners_keep_exact_fine_adjacency(self):
        local = list(product((0, 1), repeat=3))
        for offset in product((-1, 0, 1), repeat=3):
            if offset == (0, 0, 0):
                continue
            for a in local:
                for b in local:
                    pair = np.array([a, np.array(b) + 2 * np.array(offset)])
                    points = np.repeat(pair, 512, axis=0).astype(float)
                    if np.max(np.abs(pair[0] - pair[1])) <= 1:
                        expected = [list(range(1024))]
                    else:
                        expected = [list(range(512)), list(range(512, 1024))]
                        if tuple(pair[1]) < tuple(pair[0]):
                            expected.reverse()
                    self.assertEqual(spatial_components(points, 1.0), expected)

    def test_block_path_matches_pairwise_oracle_and_small_path_boundary(self):
        rng = np.random.RandomState(72)
        for count in (127, 128, 192):
            for _ in range(6):
                points = rng.randint(-6, 7, (count, 3)).astype(float)
                self.check_points(points, 1.0)
                expected = [[i * 9 + j for i in group for j in range(9)] for group in oracle(points, 1.0)]
                self.assertEqual(spatial_components(np.repeat(points, 9, axis=0), 1.0), expected)

    def test_large_coordinate_keys_and_empty_input(self):
        self.check_points(np.array([[1e7, 1e7, -1e7], [1e7 + .01, 1e7, -1e7],
                                    [-1e7, -1e7, 1e7]]))
        self.check_points(np.repeat(np.array([[1e7, 1e7, -1e7],
                                             [-1e7, -1e7, 1e7]]), 64, axis=0))
        points = np.repeat(np.array([[-1e7, -1e7, 1e7], [1e7, 1e7, -1e7]]), 512, axis=0)
        self.assertEqual(spatial_components(points), [list(range(512)), list(range(512, 1024))])
        self.check_points(np.empty((0, 3)))
