
import numpy as np


class OctreeNode:
    def __init__(self, min_coord, size, data):
        minx, miny, minz = min_coord
        sx, sy, sz = size
        sub_data = data[minz:minz + sz, miny:miny + sy, minx:minx + sx]

        # Base case: if any dimension is too small to subdivide or only one voxel
        if sx <= 1 and sy <= 1 and sz <= 1:
            self.is_leaf = True
            self.value = sub_data.flatten()[0] if sub_data.size > 0 else 0.0
            self.children = None
            return

        vals = sub_data.flatten()
        if vals.size == 0:
            self.is_leaf = True
            self.value = 0.0
            self.children = None
            return

        fluctuation = np.max(vals) - np.min(vals)

        if fluctuation <= 50:
            self.is_leaf = True
            self.value = np.mean(vals)
            self.children = None
        else:
            # Check if we can subdivide
            if min(sx, sy, sz) < 2:
                self.is_leaf = True
                self.value = np.mean(vals)
                self.children = None
                return

            self.is_leaf = False
            self.children = []

            # Compute half sizes for each dimension
            halfx = (sx + 1) // 2
            halfy = (sy + 1) // 2
            halfz = (sz + 1) // 2

            # Create 8 children
            for dx in [0, 1]:
                for dy in [0, 1]:
                    for dz in [0, 1]:
                        cx = minx + dx * halfx
                        cy = miny + dy * halfy
                        cz = minz + dz * halfz
                        csx = halfx if dx == 0 else sx - halfx
                        csy = halfy if dy == 0 else sy - halfy
                        csz = halfz if dz == 0 else sz - halfz
                        self.children.append(OctreeNode((cx, cy, cz), (csx, csy, csz), data))

    def save(self, f):
        if self.is_leaf:
            f.write(b'\x00')
            f.write(np.array([self.value], dtype='<f4').tobytes())
        else:
            f.write(b'\x01')
            for child in self.children:
                child.save(f)


def main():
    # File path in current directory
    input_file = 'saltf'

    # Dimensions from the format
    nx, ny, nz = 676, 676, 210

    # Read binary data: big-endian float32
    data = np.fromfile(input_file, dtype='>f4').reshape(nz, ny, nx)  # Assuming order: z, y, x

    # Build octree
    root = OctreeNode((0, 0, 0), (nx, ny, nz), data)

    # Save to file: little-endian
    output_file = 'octree.bin'
    with open(output_file, 'wb') as f:
        # Write header: dimensions as uint32 little-endian
        f.write(np.array([nx, ny, nz], dtype='<u4').tobytes())
        # Save the tree
        root.save(f)

    print(f"Octree saved to {output_file}")


if __name__ == "__main__":
    main()