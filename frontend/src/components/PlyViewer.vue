<!-- 
  代码功能说明：
  这是一个基于 Vue 3 和 VTK.js 的点云渲染应用，用于加载并渲染单个 PLY 格式的点云文件。
  应用通过 fetch 获取 PLY 文件，解析点云数据并在 3D 渲染窗口中显示，支持点渲染模式。
  同时支持鼠标交互，显示鼠标悬停点的 3D 坐标，并自动调整相机以适应点云的边界。

  基本流程：
  1. 初始化 VTK.js 渲染器，设置全屏渲染窗口和黑色背景。
  2. 使用 fetch 加载指定的 PLY 文件，解析为点云数据。
  3. 检查点云数据的有效性并打印调试信息（点数、单元数等）。
  4. 创建 VTK 渲染管线（Mapper 和 Actor）并添加至渲染器。
  5. 添加鼠标移动事件监听器以显示 3D 坐标。
  6. 计算点云边界，调整相机视角以适应点云。
  7. 触发渲染并显示点云。
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
import vtkCellPicker from '@kitware/vtk.js/Rendering/Core/CellPicker'; // 用于拾取鼠标位置的点

// 定义响应式变量，绑定 HTML 渲染容器
const container = ref(null);

// 组件挂载时执行的初始化逻辑
onMounted(() => {
  // 初始化 VTK 全屏渲染窗口，设置容器和背景颜色（黑色）
  const fullScreenRenderer = vtkFullScreenRenderWindow.newInstance({
    rootContainer: container.value,
    background: [0, 0, 0],
  });

  // 获取渲染器和渲染窗口
  const renderer = fullScreenRenderer.getRenderer();
  const renderWindow = fullScreenRenderer.getRenderWindow();

  // 加载 PLY 文件
  fetch('ply_chunks/pointcloud_binary_with_scalars.ply') // 指定 PLY 文件路径
    .then((response) => {
      // 将响应转换为 ArrayBuffer
      return response.arrayBuffer();
    })
    .then((arrayBuffer) => {
      // 打印缓冲区大小以便调试
      console.log('ArrayBuffer size:', arrayBuffer.byteLength);

      // 创建 PLY 文件解析器
      console.log('Creating PLY Reader...');
      const reader = vtkPLYReader.newInstance();
      // 解析 ArrayBuffer 数据
      reader.parseAsArrayBuffer(arrayBuffer);
      console.log('PLY Reader created successfully.');

      // 获取解析后的点云数据
      const polyData = reader.getOutputData();
      // 打印点云数据信息以便调试
      console.log('Number of Points:', polyData.getPoints()?.getNumberOfValues() / 3 || 0);
      console.log('PolyData Points:', polyData.getPoints());
      console.log('PolyData Cells:', polyData.getCells());

      // 检查点云数据是否有效
      if (polyData.getPoints() && polyData.getPoints().getNumberOfValues() > 0) {
        console.log('点云数据加载成功！');
      } else {
        console.error('点云数据为空或加载失败！');
        return;
      }

      // 获取点云的点数据和标量数据
      const points = polyData.getPoints();
      const pointData = polyData.getPointData();
      const scalars = pointData.getArrayByName('velocity') || pointData.getScalars();
      console.log('前 10 个点的坐标和标量值：', scalars);

      // 创建并配置 VTK Mapper，将点云数据映射到渲染对象
      const mapper = vtkPolyDataMapper.newInstance();
      mapper.setInputData(polyData);

      // 创建 VTK Actor，用于渲染点云
      const actor = vtkActor.newInstance();
      actor.setMapper(mapper);

      // 设置所有点为红色（已注释，保留默认颜色映射）
      // actor.getProperty().setColor(1, 0, 0); // RGB(1, 0, 0) -> 红色

      // 将 Actor 添加到渲染器
      renderer.addActor(actor);

      // 添加鼠标移动事件监听器，用于显示鼠标悬停点的 3D 坐标
      const interactor = renderWindow.getInteractor();
      interactor.onMouseMove((event) => {
        // 获取鼠标在窗口中的位置
        const mousePos = interactor.getEventPosition();
        // 创建并配置点拾取器，设置容差值为 0.001
        const picker = vtkCellPicker.newInstance();
        picker.setTolerance(0.001);
        // 执行拾取操作，获取鼠标位置对应的 3D 点
        picker.pick(mousePos[0], mousePos[1], 0, renderer);

        const pickedPosition = picker.getPickPosition();
        if (pickedPosition) {
          // 如果拾取到点，获取其 3D 坐标并显示
          const [x, y, z] = pickedPosition;
          document.getElementById('coordinate-display').innerText = `X: ${x.toFixed(2)}, Y: ${y.toFixed(2)}, Z: ${z.toFixed(2)}`;
        }
      });

      // 计算点云的边界框 [xmin, xmax, ymin, ymax, zmin, zmax]
      const bounds = polyData.getBounds();

      // 计算模型中心点
      const center = [
        (bounds[0] + bounds[1]) / 2, // x中心
        (bounds[2] + bounds[3]) / 2, // y中心
        (bounds[4] + bounds[5]) / 2, // z中心
      ];

      // 计算模型尺寸
      const size = [
        bounds[1] - bounds[0], // x尺寸
        bounds[3] - bounds[2], // y尺寸
        bounds[5] - bounds[4], // z尺寸
      ];

      // 设置相机位置，自动适应模型
      const camera = renderer.getActiveCamera();
      const distance = Math.max(...size) * 1.5; // 相机距离模型 1.5 倍最大尺寸
      camera.setPosition(center[0], center[1], center[2] + distance); // 设置相机位置
      camera.setFocalPoint(center[0], center[1], center[2]); // 设置相机焦点为中心

      // 重置相机并触发渲染
      renderer.resetCamera();
      renderWindow.render();
    })
    .catch((error) => {
      // 处理加载或解析错误
      console.error('Error loading pointcloud.ply:', error);
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