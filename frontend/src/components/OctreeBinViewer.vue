<!-- 
  代码功能说明：
  本组件基于 Vue 3 和 VTK.js，实现从自定义二进制八叉树数据格式（octree.bin）中解析体数据并进行体渲染。
  数据通过递归方式从二进制文件中解析为三维标量体素数据，使用颜色映射和不透明度函数进行可视化。
  应用适用于自定义体数据的渲染调试场景，并使用全屏渲染器和离屏缓冲提升渲染效率。

  基本流程：
  1. 初始化 VTK.js 全屏渲染窗口，挂载到容器并设置黑色背景。
  2. 通过 fetch 加载二进制八叉树数据（octree.bin），递归解码为体素数组。
  3. 构建 vtkImageData 容器封装数据，设置维度、间距等基础信息。
  4. 创建渲染管线（VolumeMapper + Volume），设置采样距离平衡性能和质量。
  5. 定义颜色传输函数和不透明度映射函数，实现标量值视觉映射。
  6. 渲染器添加体对象，重置相机并执行初始渲染。
-->

<template>
  <!-- 渲染容器，用于挂载 VTK 的 WebGL 渲染窗口 -->
  <div ref="container" class="vtk-container"></div>
</template>

<script setup>
import { onMounted, ref } from 'vue';

import '@kitware/vtk.js/favicon';
import '@kitware/vtk.js/Rendering/Profiles/Volume'; // 加载体渲染功能集

import vtkFullScreenRenderWindow from '@kitware/vtk.js/Rendering/Misc/FullScreenRenderWindow'; // 创建全屏渲染窗口
import vtkVolume from '@kitware/vtk.js/Rendering/Core/Volume'; // VTK 体渲染对象
import vtkVolumeMapper from '@kitware/vtk.js/Rendering/Core/VolumeMapper'; // 映射体数据到图像
import vtkColorTransferFunction from '@kitware/vtk.js/Rendering/Core/ColorTransferFunction'; // 颜色映射函数
import vtkPiecewiseFunction from '@kitware/vtk.js/Common/DataModel/PiecewiseFunction'; // 不透明度映射函数
import vtkImageData from '@kitware/vtk.js/Common/DataModel/ImageData'; // 三维图像数据容器
import vtkDataArray from '@kitware/vtk.js/Common/Core/DataArray'; // 数据数组封装体素值
import vtkBoundingBox from '@kitware/vtk.js/Common/DataModel/BoundingBox'; // 空间边界计算工具

// 创建响应式 DOM 引用，绑定至 template 中容器
const container = ref(null);

// 挂载后执行初始化逻辑
onMounted(() => {
  // 创建全屏渲染窗口并绑定到容器，设置背景为黑色并启用离屏缓冲
  const fullScreenRenderer = vtkFullScreenRenderWindow.newInstance({
    rootContainer: container.value,
    background: [0, 0, 0],
    useOffscreenBuffers: true,
  });

  // 获取渲染器和渲染窗口句柄
  const renderer = fullScreenRenderer.getRenderer();
  const renderWindow = fullScreenRenderer.getRenderWindow();

  const t0 = performance.now(); // ⏱️ 开始加载计时

  // 加载自定义 octree.bin 数据文件
  fetch('/octree.bin')
    .then(response => response.arrayBuffer())
    .then(arrayBuffer => {
      const t1 = performance.now();
      console.log(`📦 模型加载时间（fetch + arrayBuffer）: ${(t1 - t0).toFixed(2)} ms`);

      const view = new DataView(arrayBuffer);

      // 读取体数据的维度信息 nx × ny × nz
      let pos = 0;
      const nx = view.getUint32(pos, true); pos += 4;
      const ny = view.getUint32(pos, true); pos += 4;
      const nz = view.getUint32(pos, true); pos += 4;

      const totalVoxels = nx * ny * nz;
      console.log(`🔵 体素数量: ${totalVoxels} 点`);

      // 打印当前页面内存使用情况
      if (performance.memory) {
        const used = (performance.memory.usedJSHeapSize / 1024 / 1024).toFixed(2);
        const total = (performance.memory.totalJSHeapSize / 1024 / 1024).toFixed(2);
        const limit = (performance.memory.jsHeapSizeLimit / 1024 / 1024).toFixed(2);
        console.log(`💾 内存使用: 已用 ${used} MB / 分配 ${total} MB / 限制 ${limit} MB`);
      } else {
        console.warn('⚠️ 当前浏览器不支持 performance.memory');
      }

      const t2 = performance.now(); // ⏱️ 构建八叉树开始
      // 创建体素标量数据数组
      const data = new Float32Array(totalVoxels);

      // 递归解析八叉树体素节点
      const parseNode = (minx, miny, minz, sx, sy, sz) => {
        const byte = view.getUint8(pos); pos++;
        if (byte === 0) {
          const value = view.getFloat32(pos, true); pos += 4;
          for (let dz = 0; dz < sz; dz++) {
            for (let dy = 0; dy < sy; dy++) {
              for (let dx = 0; dx < sx; dx++) {
                const x = minx + dx;
                const y = miny + dy;
                const z = minz + dz;
                const idx = z * ny * nx + y * nx + x;
                data[idx] = value;
              }
            }
          }
        } else {
          const halfx = Math.floor((sx + 1) / 2);
          const halfy = Math.floor((sy + 1) / 2);
          const halfz = Math.floor((sz + 1) / 2);
          for (let dz = 0; dz < 2; dz++) {
            for (let dy = 0; dy < 2; dy++) {
              for (let dx = 0; dx < 2; dx++) {
                const cx = minx + dx * halfx;
                const cy = miny + dy * halfy;
                const cz = minz + dz * halfz;
                const csx = dx === 0 ? halfx : sx - halfx;
                const csy = dy === 0 ? halfy : sy - halfy;
                const csz = dz === 0 ? halfz : sz - halfz;
                parseNode(cx, cy, cz, csx, csy, csz);
              }
            }
          }
        }
      };

      // 启动八叉树解析
      parseNode(0, 0, 0, nx, ny, nz);
      const t3 = performance.now();
      console.log(`🌲 八叉树体素构建时间: ${(t3 - t2).toFixed(2)} ms`);

      // 创建 vtkImageData 对象并设置基础属性
      const imageData = vtkImageData.newInstance();
      imageData.setDimensions(nx, ny, nz);
      imageData.setOrigin(0, 0, 0);
      imageData.setSpacing(20, 20, 20); // 设置每个体素间距（单位 mm）

      // 封装体素数据为 VTK 数据数组，并绑定到 imageData
      const scalars = vtkDataArray.newInstance({
        name: 'scalars',
        values: data,
        numberOfComponents: 1,
      });
      imageData.getPointData().setScalars(scalars);

      // 获取标量值范围（用于颜色和透明度映射）
      const dataRange = scalars.getRange();

      // 创建体渲染对象和 Mapper，并绑定数据
      const actor = vtkVolume.newInstance();
      const mapper = vtkVolumeMapper.newInstance();
      mapper.setInputData(imageData);

      const sampleDistance = 0.7 * Math.sqrt(
        imageData.getSpacing().map(v => v * v).reduce((a, b) => a + b, 0)
      );
      mapper.setSampleDistance(sampleDistance);
      actor.setMapper(mapper);

      const ctfun = vtkColorTransferFunction.newInstance();
      ctfun.addRGBPoint(dataRange[0], 0.0, 0.0, 1.0);
      ctfun.addRGBPoint((dataRange[0] + dataRange[1]) / 2, 0.0, 1.0, 0.0);
      ctfun.addRGBPoint(dataRange[1], 1.0, 0.0, 0.0);

      const ofun = vtkPiecewiseFunction.newInstance();
      ofun.addPoint(dataRange[0], 0.0);
      ofun.addPoint(dataRange[1], 0.4);

      const prop = actor.getProperty();
      prop.setRGBTransferFunction(0, ctfun);
      prop.setScalarOpacity(0, ofun);
      prop.setScalarOpacityUnitDistance(
        0,
        vtkBoundingBox.getDiagonalLength(imageData.getBounds()) /
        Math.max(...imageData.getDimensions())
      );
      prop.setInterpolationTypeToLinear();
      prop.setGradientOpacityMinimumValue(0, 0);
      prop.setGradientOpacityMaximumValue(0, (dataRange[1] - dataRange[0]) * 0.05);
      prop.setAmbient(0.2);
      prop.setDiffuse(0.7);
      prop.setSpecular(0.3);
      prop.setSpecularPower(8.0);

      // 添加体对象到渲染器，重置相机并渲染
      renderer.addVolume(actor);
      renderer.resetCamera();
      renderWindow.render();

      const t4 = performance.now();
      console.log(`🖼️ 渲染阶段耗时（构建完成 → 画面显示）: ${(t4 - t3).toFixed(2)} ms`);
      console.log(`⏱️ 总耗时（从 fetch 开始 → 渲染完成）: ${(t4 - t0).toFixed(2)} ms`);
    });
});
</script>

<style scoped>
/* 渲染容器样式，占满整个视口，高性能渲染布局 */
.vtk-container {
  width: 100%;
  height: 100vh;
  overflow: hidden;
}
</style>
