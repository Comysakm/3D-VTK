import numpy as np


class PointOctreeNode:
    """
    点八叉树节点类，每个叶子节点代表一个采样点而不是体素块
    """

    def __init__(self, min_coord, size, data, max_depth=10, current_depth=0):
        minx, miny, minz = min_coord
        sx, sy, sz = size

        # 检查是否达到最大深度或空间太小
        if current_depth >= max_depth or min(sx, sy, sz) <= 1:
            self.is_leaf = True
            # 选择该区域的代表性采样点（中心点）
            center_x = minx + sx // 2
            center_y = miny + sy // 2
            center_z = minz + sz // 2

            # 获取中心点的值作为该节点的代表值
            if 0 <= center_x < data.shape[2] and 0 <= center_y < data.shape[1] and 0 <= center_z < data.shape[0]:
                self.value = data[center_z, center_y, center_x]
            else:
                self.value = 0.0

            self.position = (center_x, center_y, center_z)  # 存储采样点坐标
            self.children = None
            return

        # 获取该子空间的数据
        sub_data = data[minz:minz + sz, miny:miny + sy, minx:minx + sx]
        vals = sub_data.flatten()

        if vals.size == 0:
            self.is_leaf = True
            self.value = 0.0
            # 使用区域中心作为默认位置
            self.position = (minx + sx // 2, miny + sy // 2, minz + sz // 2)
            self.children = None
            return

        # 计算该区域的波动性
        fluctuation = np.max(vals) - np.min(vals)

        if fluctuation <= 50:
            # 波动小，创建叶子节点（采样中心点）
            self.is_leaf = True
            center_x = minx + sx // 2
            center_y = miny + sy // 2
            center_z = minz + sz // 2

            if 0 <= center_x < data.shape[2] and 0 <= center_y < data.shape[1] and 0 <= center_z < data.shape[0]:
                self.value = data[center_z, center_y, center_x]
            else:
                self.value = np.mean(vals) if vals.size > 0 else 0.0

            self.position = (center_x, center_y, center_z)
            self.children = None
        else:
            # 波动大，需要细分
            if min(sx, sy, sz) < 2:
                # 空间太小，无法进一步细分，创建叶子节点
                self.is_leaf = True
                center_x = minx + sx // 2
                center_y = miny + sy // 2
                center_z = minz + sz // 2

                if 0 <= center_x < data.shape[2] and 0 <= center_y < data.shape[1] and 0 <= center_z < data.shape[0]:
                    self.value = data[center_z, center_y, center_x]
                else:
                    self.value = np.mean(vals) if vals.size > 0 else 0.0

                self.position = (center_x, center_y, center_z)
                self.children = None
                return

            # 创建内部节点
            self.is_leaf = False
            self.children = []

            # 计算各维度的一半大小
            halfx = (sx + 1) // 2
            halfy = (sy + 1) // 2
            halfz = (sz + 1) // 2

            # 创建8个子节点
            for dz in [0, 1]:
                for dy in [0, 1]:
                    for dx in [0, 1]:
                        cx = minx + dx * halfx
                        cy = miny + dy * halfy
                        cz = minz + dz * halfz
                        csx = halfx if dx == 0 else sx - halfx
                        csy = halfy if dy == 0 else sy - halfy
                        csz = halfz if dz == 0 else sz - halfz

                        # 递归创建子节点，传递当前深度
                        child_node = PointOctreeNode(
                            (cx, cy, cz),
                            (csx, csy, csz),
                            data,
                            max_depth,
                            current_depth + 1
                        )
                        self.children.append(child_node)

    def save(self, f):
        """
        保存点八叉树节点到文件
        格式：节点类型(1字节) + [如果是叶子：值(4字节) + x(4字节) + y(4字节) + z(4字节)]
              [如果是内部节点：直接递归保存子节点]
        """
        if self.is_leaf:
            # 叶子节点：类型0 + 标量值 + 3D坐标
            f.write(b'\x00')
            # 写入标量值 (little-endian float32)
            f.write(np.array([self.value], dtype='<f4').tobytes())
            # 写入坐标 (little-endian float32，每个坐标4字节)
            coords = np.array(self.position, dtype='<f4')
            f.write(coords.tobytes())
        else:
            # 内部节点：类型1 + 8个子节点
            f.write(b'\x01')
            for child in self.children:
                child.save(f)

    def get_leaf_points(self):
        """
        获取所有叶子节点（采样点）的列表
        返回：[(x, y, z, value), ...] 格式的列表
        """
        points = []

        if self.is_leaf:
            x, y, z = self.position
            points.append((x, y, z, self.value))
        else:
            for child in self.children:
                points.extend(child.get_leaf_points())

        return points


def main():
    """
    主函数：从体素数据构建点八叉树并保存
    """
    # 输入文件路径
    input_file = 'Saltf'

    # 维度配置（来自原始文件格式）
    nx, ny, nz = 676, 676, 210

    print(f"正在从体素数据构建点八叉树...")
    print(f"输入维度：{nx} × {ny} × {nz}")

    # 读取二进制数据：大端序 float32
    print("读取体素数据...")
    data = np.fromfile(input_file, dtype='>f4').reshape(nz, ny, nx)
    print(f"数据范围：[{data.min():.2f}, {data.max():.2f}]")

    # 计算最大深度（基于较小维度）
    max_depth = int(np.log2(min(nx, ny, nz))) + 1
    print(f"最大八叉树深度：{max_depth}")

    # 构建点八叉树
    print("构建点八叉树...")
    root = PointOctreeNode((0, 0, 0), (nx, ny, nz), data, max_depth=max_depth)

    # 获取所有采样点用于验证
    all_points = root.get_leaf_points()
    print(f"生成采样点数量：{len(all_points):,}")

    if all_points:
        point_values = [p[3] for p in all_points]
        print(f"采样点值范围：[{min(point_values):.2f}, {max(point_values):.2f}]")

    # 保存到文件：小端序
    output_file = 'point_octree.bin'
    print(f"保存点八叉树到 {output_file}...")

    with open(output_file, 'wb') as f:
        # 写入头部：维度 (little-endian uint32)
        f.write(np.array([nx, ny, nz], dtype='<u4').tobytes())
        # 保存八叉树结构
        root.save(f)

    # 计算文件大小
    file_size = os.path.getsize(output_file)
    points_per_byte = len(all_points) / file_size if file_size > 0 else 0
    print(f"文件大小：{file_size / 1024:.1f} KB")
    print(f"每字节存储点数：{points_per_byte:.2f}")
    print(f"点八叉树保存完成：{output_file}")


if __name__ == "__main__":
    import os  # 用于获取文件大小

    main()