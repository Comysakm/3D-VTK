<!-- 
  代码功能说明：
  这是一个基于 Vue 3 和 VTK.js 的体视显微镜数据体渲染应用，用于加载 VTI 格式的体数据并进行体渲染。
  应用通过颜色映射和不透明度映射函数对体数据的标量值进行可视化，突出不同标量值区域，并使用离屏缓冲优化渲染性能。

  基本流程：
  1. 初始化 VTK.js 渲染器，设置全屏渲染窗口和黑色背景，启用离屏缓冲。
  2. 使用 fetch 加载 VTI 文件，解析体视显微镜数据。
  3. 创建体渲染管线（VolumeMapper 和 Volume），配置采样距离。
  4. 设置颜色映射（RGB）和不透明度映射，定义标量值对应的颜色和透明度。
  5. 将体对象添加到渲染器，调整相机并触发渲染。
-->

<template>
  <!-- 渲染容器，用于挂载 VTK 的 WebGL 渲染窗口 -->
  <div ref="container" class="vtk-container"></div>
</template>

<script setup>
import { onMounted, ref } from 'vue';
import '@kitware/vtk.js/Rendering/Profiles/Volume'; // 加载 VTK.js 的体渲染模块
import vtkFullScreenRenderWindow from '@kitware/vtk.js/Rendering/Misc/FullScreenRenderWindow'; // 用于创建全屏渲染窗口
import vtkXMLImageDataReader from '@kitware/vtk.js/IO/XML/XMLImageDataReader'; // 用于解析 VTI 文件
import vtkVolume from '@kitware/vtk.js/Rendering/Core/Volume'; // VTK 体渲染对象
import vtkVolumeMapper from '@kitware/vtk.js/Rendering/Core/VolumeMapper'; // 用于映射体数据到渲染对象
import vtkColorTransferFunction from '@kitware/vtk.js/Rendering/Core/ColorTransferFunction'; // 用于颜色映射
import vtkPiecewiseFunction from '@kitware/vtk.js/Common/DataModel/PiecewiseFunction'; // 用于不透明度映射

// 定义响应式变量，绑定 HTML 渲染容器
const container = ref(null);

// 组件挂载时执行的初始化逻辑
onMounted(() => {
  // 创建全屏渲染窗口，启用离屏缓冲以优化体渲染性能
  const fullScreenRenderer = vtkFullScreenRenderWindow.newInstance({
    rootContainer: container.value,
    background: [0, 0, 0], // 设置背景为黑色
    useOffscreenBuffers: true, // 启用离屏渲染以提高性能
  });

  // 获取渲染器和渲染窗口
  const renderer = fullScreenRenderer.getRenderer();
  const renderWindow = fullScreenRenderer.getRenderWindow();

  // 检查浏览器是否支持 WebGL 2.0（用于调试性能）
  const isWebGL2 = !!window.WebGL2RenderingContext;
  console.log('WebGL 2.0 supported:', isWebGL2);

  // 使用 fetch 加载 VTI 文件
  fetch('/SaltfF.vti')
    .then(response => response.arrayBuffer()) // 获取文件数据的 ArrayBuffer
    .then(arrayBuffer => {
      // 创建 VTI 文件解析器并解析数据
      const reader = vtkXMLImageDataReader.newInstance();
      reader.parseAsArrayBuffer(arrayBuffer);
      const imageData = reader.getOutputData(0); // 获取解析后的体数据

      // 创建并配置 VolumeMapper，设置采样距离以平衡质量和性能
      const mapper = vtkVolumeMapper.newInstance();
      mapper.setSampleDistance(2.0); // 采样距离：较小值提高质量，较大值提升性能
      mapper.setInputData(imageData);

      // 创建体渲染对象并绑定 Mapper
      const volume = vtkVolume.newInstance();
      volume.setMapper(mapper);

      // 配置颜色映射函数，映射标量值到颜色
      const ctfun = vtkColorTransferFunction.newInstance();
      ctfun.addRGBPoint(1500, 0, 0.3, 0.3); // 低值映射为暗红色
      ctfun.addRGBPoint(2477.0, 0.0, 0.8, 0.8); // 中间值映射为青色
      ctfun.addRGBPoint(4482.0, 1.0, 1.0, 1.0); // 高值映射为白色

      // 配置不透明度映射函数，控制体素可见性
      const ofun = vtkPiecewiseFunction.newInstance();
      ofun.addPoint(1500, 0.0); // 低值完全透明
      ofun.addPoint(2477.0, 0.3); // 中间值部分透明
      ofun.addPoint(4482.0, 0.6); // 高值较不透明

      // 配置体渲染属性
      const property = volume.getProperty();
      property.setRGBTransferFunction(0, ctfun); // 设置颜色映射
      property.setScalarOpacity(0, ofun); // 设置不透明度映射
      property.setInterpolationTypeToLinear(); // 使用线性插值以平滑过渡

      // 将体对象添加到渲染器
      renderer.addVolume(volume);

      // 重置相机以适应体数据
      renderer.resetCamera();
      // 触发初始渲染
      renderWindow.render();
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