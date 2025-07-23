<!-- 
  代码功能说明：
  这是一个基于 Vue 3 和 VTK.js 的点云渲染应用，用于加载并渲染多个分块的 PLY 格式点云文件。
  应用通过并行加载多个 PLY 文件（每个文件表示点云的一部分），解析并渲染点云数据，支持颜色映射和点渲染模式。
  渲染完成后，自动调整相机以适应点云的边界。

  基本流程：
  1. 初始化 VTK.js 渲染器，设置全屏渲染窗口和黑色背景。
  2. 动态生成多个 PLY 分块文件的路径（假设为 5 个分块）。
  3. 并行加载所有 PLY 文件，解析点云数据，检查点数和标量数据。
  4. 为每个有效分块创建 VTK 渲染管线（Mapper 和 Actor），并应用颜色映射。
  5. 将所有分块的 Actor 添加到渲染器，合并边界以调整相机视角。
  6. 触发渲染并显示点云。
-->

<template>
  <!-- VTK 渲染容器，用于显示 3D 点云 -->
  <div ref="container" class="vtk-container"></div>
</template>

<script setup>
import { onMounted, ref } from 'vue';
import '@kitware/vtk.js/Rendering/Profiles/Geometry'; // 加载 VTK.js 的几何渲染模块
import vtkFullScreenRenderWindow from '@kitware/vtk.js/Rendering/Misc/FullScreenRenderWindow'; // 用于创建全屏渲染窗口
import vtkPLYReader from '@kitware/vtk.js/IO/Geometry/PLYReader'; // 用于解析 PLY 文件
import vtkActor from '@kitware/vtk.js/Rendering/Core/Actor'; // VTK 渲染对象
import vtkPolyDataMapper from '@kitware/vtk.js/Rendering/Core/Mapper'; // 用于映射点云数据到渲染对象
import vtkColorTransferFunction from '@kitware/vtk.js/Rendering/Core/ColorTransferFunction'; // 用于颜色映射

// 定义响应式变量，用于引用渲染容器 DOM 元素
const container = ref(null);

// 组件挂载时执行的初始化逻辑
onMounted(() => {
  console.log('Initializing vtk.js renderer...');
  // 初始化 VTK 全屏渲染窗口，设置容器和背景颜色（黑色）
  const fullScreenRenderer = vtkFullScreenRenderWindow.newInstance({
    rootContainer: container.value,
    background: [0, 0, 0],
  });

  // 获取渲染器和渲染窗口
  const renderer = fullScreenRenderer.getRenderer();
  const renderWindow = fullScreenRenderer.getRenderWindow();

  // 异步函数，用于加载并渲染多个 PLY 分块文件
  async function loadChunks() {
    // 定义分块文件路径数组（假设 5 个分块，需根据实际文件调整）
    const chunkFiles = [];
    for (let i = 0; i < 5; i++) {
      chunkFiles.push(`ply_chunks1/pointcloud_binary_part_${i}.ply`);
    }

    // 并行加载所有分块文件
    const promises = chunkFiles.map(async (file) => {
      try {
        // 记录开始加载分块文件
        console.log(`Fetching chunk: ${file}`);
        // 通过 fetch 获取 PLY 文件
        const response = await fetch(file);
        if (!response.ok) {
          console.warn(`Failed to load ${file}: HTTP ${response.status}`);
          return null;
        }
        // 获取文件数据的 ArrayBuffer
        const arrayBuffer = await response.arrayBuffer();
        console.log(`Chunk ${file} ArrayBuffer size:`, arrayBuffer.byteLength);

        // 检查文件是否为空
        if (arrayBuffer.byteLength === 0) {
          console.warn(`Chunk ${file} is empty!`);
          return null;
        }

        // 创建 PLY 文件解析器并解析数据
        const reader = vtkPLYReader.newInstance();
        console.time(`parse_${file}`);
        reader.parseAsArrayBuffer(arrayBuffer);
        console.timeEnd(`parse_${file}`);

        // 获取解析后的点云数据
        const polyData = reader.getOutputData();
        // 计算点云中的点数（顶点数 / 3）
        const numPoints = polyData.getPoints()?.getNumberOfValues() / 3 || 0;
        console.log(`Chunk ${file} Number of Points:`, numPoints);
        console.log(`Chunk ${file} Number of Cells:`, polyData.getNumberOfCells());
        console.log(`Chunk ${file} Bounds:`, polyData.getBounds());

        // 打印前 10 个点的坐标和标量值（用于调试）
        const points = polyData.getPoints();
        const pointData = polyData.getPointData();
        const scalars = pointData.getArrayByName('x') || pointData.getScalars();
        if (points && numPoints > 0) {
          console.log(`Chunk ${file} First 10 points:`);
          const pointValues = points.getData();
          const scalarValues = scalars ? scalars.getData() : null;
          for (let j = 0; j < Math.min(10, numPoints); j++) {
            const x = pointValues[j * 3];
            const y = pointValues[j * 3 + 1];
            const z = pointValues[j * 3 + 2];
            const volume = scalarValues ? scalarValues[j] : 'N/A';
            console.log(`Point ${j}: x=${x}, y=${y}, z=${z}, volume=${volume}`);
          }
        } else {
          console.warn(`No valid points in ${file}`);
          return null;
        }

        // 检查标量数据是否存在
        if (scalars) {
          console.log(`Chunk ${file} Scalar Array Name:`, scalars.getName());
          console.log(`Chunk ${file} Scalar Range:`, scalars.getRange());
          console.log(`Chunk ${file} Scalar Data (first 10):`, scalars.getData().slice(0, 10));
        } else {
          console.warn(`No scalar data in ${file}`);
          return null;
        }

        // 检查点云数据是否有效
        if (!polyData.getPoints() || polyData.getPoints().getNumberOfValues() === 0) {
          console.warn(`No valid points in ${file}`);
          return null;
        }

        // 创建并配置 VTK Mapper，将点云数据映射到渲染对象
        const mapper = vtkPolyDataMapper.newInstance();
        mapper.setInputData(polyData);
        mapper.setScalarVisibility(true); // 启用标量可视化
        mapper.setScalarModeToUsePointData(); // 使用点数据
        mapper.setColorModeToMapScalars(); // 映射标量到颜色

        // 创建颜色查找表并设置颜色映射
        const lut = vtkColorTransferFunction.newInstance();
        const scalarRange = scalars.getRange();
        console.log(`Applying scalar range: ${scalarRange}`);
        lut.addRGBPoint(scalarRange[0], 0, 0, 1); // 最小值映射为蓝色
        lut.addRGBPoint((scalarRange[0] + scalarRange[1]) / 2, 0, 1, 0); // 中间值映射为绿色
        lut.addRGBPoint(scalarRange[1], 1, 0, 0); // 最大值映射为红色
        mapper.setLookupTable(lut);
        mapper.setScalarRange(scalarRange[0], scalarRange[1]); // 设置标量范围

        // 创建 VTK Actor，用于渲染点云
        const actor = vtkActor.newInstance();
        // 设置所有点为红色（覆盖颜色映射，仅用于调试）
        actor.getProperty().setColor(1, 0, 0); // RGB(1, 0, 0) -> 红色
        actor.setMapper(mapper);
        actor.getProperty().setRepresentation(0); // 设置为点渲染模式
        actor.getProperty().setPointSize(5); // 设置点大小为 5

        // 返回 Actor 和点云边界
        return { actor, bounds: polyData.getBounds() };
      } catch (error) {
        console.error(`Error loading ${file}:`, error);
        return null;
      }
    });

    // 等待所有分块加载完成
    const results = await Promise.all(promises);
    let bounds = null;
    // 遍历加载结果，添加有效 Actor 并合并边界
    results.forEach((result) => {
      if (result) {
        renderer.addActor(result.actor);
        const chunkBounds = result.bounds;
        if (!bounds) {
          bounds = [...chunkBounds];
        } else {
          // 更新全局边界，合并所有分块的边界
          bounds[0] = Math.min(bounds[0], chunkBounds[0]);
          bounds[1] = Math.max(bounds[1], chunkBounds[1]);
          bounds[2] = Math.min(bounds[2], chunkBounds[2]);
          bounds[3] = Math.max(bounds[3], chunkBounds[3]);
          bounds[4] = Math.min(bounds[4], chunkBounds[4]);
          bounds[5] = Math.max(bounds[5], chunkBounds[5]);
        }
      }
    });

    // 调整相机以适应点云整体边界
    if (bounds) {
      // 计算边界中心
      const center = [
        (bounds[0] + bounds[1]) / 2,
        (bounds[2] + bounds[3]) / 2,
        (bounds[4] + bounds[5]) / 2,
      ];
      // 计算边界最大尺寸
      const size = Math.max(bounds[1] - bounds[0], bounds[3] - bounds[2], bounds[5] - bounds[4]) || 1;
      const camera = renderer.getActiveCamera();
      // 设置相机位置和焦点
      camera.setPosition(center[0], center[1], center[2] + size * 1.5);
      camera.setFocalPoint(center[0], center[1], center[2]);
      renderer.resetCamera();
    }

    // 触发渲染
    console.log('Starting render...');
    renderWindow.render();
    console.log('Render complete.');
  }

  // 执行分块加载并处理错误
  loadChunks().catch((error) => {
    console.error('Error in loadChunks:', error);
  });
});
</script>

<style scoped>
/* 渲染容器样式，占满视口宽度和高度，隐藏溢出内容 */
.vtk-container {
  width: 100%;
  height: 100vh;
  overflow: hidden;
}
</style>