import struct
import sys


def count_octree_points(filename):
    """
    统计八叉树文件的体素点数
    """
    total_points = 0
    leaf_points = 0
    internal_nodes = 0

    try:
        with open(filename, 'rb') as f:
            # 读取头部：3个uint32 (nx, ny, nz) - little-endian
            header_data = f.read(12)
            if len(header_data) < 12:
                print(f"错误：文件 {filename} 太小，无法包含头部信息")
                return

            nx, ny, nz = struct.unpack('<III', header_data)
            total_voxels = nx * ny * nz
            print(f"维度：{nx} × {ny} × {nz}")
            print(f"总体素数：{total_voxels:,}")
            print("-" * 50)

            # 递归解析八叉树
            def parse_node():
                nonlocal total_points, leaf_points, internal_nodes

                # 读取节点类型 (1字节)
                node_type = f.read(1)
                if len(node_type) == 0:
                    return False  # EOF

                is_leaf = (node_type[0] == 0)

                if is_leaf:
                    # 叶子节点：读取float32值
                    value_data = f.read(4)
                    if len(value_data) < 4:
                        print("错误：叶子节点数据不完整")
                        return False

                    leaf_points += 1
                    total_points += 1  # 每个叶子节点代表至少1个体素
                else:
                    internal_nodes += 1
                    total_points += 1  # 内部节点也贡献体素

                    # 递归处理8个子节点
                    for _ in range(8):
                        if not parse_node():
                            return False

                return True

            # 开始解析
            if parse_node():
                print(f"\n八叉树统计：")
                print(f"总节点数：{total_points:,}")
                print(f"叶子节点数：{leaf_points:,}")
                print(f"内部节点数：{internal_nodes:,}")
                print(f"压缩比：{total_voxels / total_points:.2f} 倍")
                print(f"内存节省：{(1 - total_points / total_voxels) * 100:.1f}%")
            else:
                print("错误：无法完全解析八叉树")

    except FileNotFoundError:
        print(f"错误：找不到文件 {filename}")
    except Exception as e:
        print(f"读取文件错误：{e}")


def detailed_octree_analysis(filename):
    """
    详细的八叉树分析，包括每个级别的信息
    """
    try:
        with open(filename, 'rb') as f:
            # 读取头部
            header_data = f.read(12)
            if len(header_data) < 12:
                print(f"错误：文件 {filename} 太小")
                return

            nx, ny, nz = struct.unpack('<III', header_data)
            total_voxels = nx * ny * nz

            print(f"详细八叉树分析 - {filename}")
            print(f"维度：{nx} × {ny} × {nz}")
            print(f"总体素数：{total_voxels:,}")
            print("=" * 60)

            # 跟踪当前级别和节点尺寸
            level_stats = {}

            def parse_node_detailed(size_x, size_y, size_z, current_level):
                nonlocal f

                node_type = f.read(1)
                if len(node_type) == 0:
                    return 0, 0, 0

                is_leaf = (node_type[0] == 0)
                voxels_in_node = size_x * size_y * size_z

                # 统计每个级别的信息
                if current_level not in level_stats:
                    level_stats[current_level] = {'leaves': 0, 'internals': 0, 'voxels': 0}

                if is_leaf:
                    # 叶子节点
                    f.read(4)  # 跳过值
                    level_stats[current_level]['leaves'] += 1
                    level_stats[current_level]['voxels'] += voxels_in_node
                    return voxels_in_node, 1, 0
                else:
                    # 内部节点
                    level_stats[current_level]['internals'] += 1

                    total_voxels_in_subtree = 0
                    total_leaf_nodes = 0
                    total_internal_nodes = 0

                    # 计算子节点尺寸
                    half_x = (size_x + 1) // 2
                    half_y = (size_y + 1) // 2
                    half_z = (size_z + 1) // 2

                    child_sizes = [
                        (half_x, half_y, half_z),
                        (half_x, half_y, size_z - half_z),
                        (half_x, size_y - half_y, half_z),
                        (half_x, size_y - half_y, size_z - half_z),
                        (size_x - half_x, half_y, half_z),
                        (size_x - half_x, half_y, size_z - half_z),
                        (size_x - half_x, size_y - half_y, half_z),
                        (size_x - half_x, size_y - half_y, size_z - half_z)
                    ]

                    for child_size in child_sizes:
                        cvx, cly, cin = parse_node_detailed(*child_size, current_level + 1)
                        total_voxels_in_subtree += cvx
                        total_leaf_nodes += cly
                        total_internal_nodes += cin

                    return total_voxels_in_subtree, total_leaf_nodes, total_internal_nodes + 1

            total_voxels_counted, total_leaves, total_internals = parse_node_detailed(nx, ny, nz, 0)

            print(f"\n详细统计：")
            print(f"总表示体素数：{total_voxels_counted:,}")
            print(f"叶子节点数：{total_leaves:,}")
            print(f"内部节点数：{total_internals:,}")
            print(f"总节点数：{total_leaves + total_internals:,}")
            print(f"压缩比：{total_voxels / (total_leaves + total_internals):.2f} 倍")
            print(f"平均每个叶子节点体素数：{total_voxels / total_leaves:.1f}")

            # 打印各级别统计
            print(f"\n各级别统计：")
            print(f"{'级别':<6} {'叶子节点':<10} {'内部节点':<12} {'体素数':<12} {'平均尺寸':<10}")
            print("-" * 50)

            for level in sorted(level_stats.keys()):
                stats = level_stats[level]
                avg_size = stats['voxels'] / stats['leaves'] if stats['leaves'] > 0 else 0
                print(
                    f"{level:<6} {stats['leaves']:<10} {stats['internals']:<12} {stats['voxels']:<12,} {avg_size:<10.1f}")

            if total_voxels_counted != total_voxels:
                print(f"\n警告：体素数不匹配！预期：{total_voxels:,}，实际：{total_voxels_counted:,}")

    except Exception as e:
        print(f"错误：{e}")


def analyze_octree_file(filename="octree.bin"):
    """
    分析八叉树文件的主函数
    """
    print(f"=== 八叉树统计分析 ===")
    print(f"文件：{filename}")
    print("=" * 50)

    # 快速统计
    print("\n1. 快速统计：")
    count_octree_points(filename)

    # 详细分析
    print("\n2. 详细分析：")
    detailed_octree_analysis(filename)

    print("\n" + "=" * 50)
    print("分析完成。")


if __name__ == "__main__":
    # 配置参数
    OCTREE_FILE = "octree.bin"  # 八叉树文件名

    # 运行分析
    analyze_octree_file(OCTREE_FILE)