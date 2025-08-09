<!--
  代码功能说明：
  这是一个基于 Vue 3 和 VTK.js 的三维点云可视化测试应用，用于测试 VTK.js 渲染大规模点云（以立方体形式显示）的性能。点云数据在脚本中随机生成，用户可通过修改脚本中的变量配置点数量、立方体大小模式（统一大小或随机大小）、随机大小种类及比例。渲染完成后，生成性能日志，记录测试目标、内存占用、模型大小、点数量、渲染时间和立方体大小分布，显示在控制台。

  主要功能：
  1. 初始化 VTK.js 渲染器，设置全屏渲染窗口和深灰色背景。
  2. 通过脚本变量配置点数量（每轴点数）、立方体大小模式（统一或随机）、随机大小种类及比例。
  3. 生成随机点云数据，存储为 vtkPolyData，点位置按规则网格排列。
  4. 使用 vtkGlyph3DMapper 将点云渲染为立方体，统一大小或按随机大小缩放。
  5. 根据立方体大小应用蓝-绿-红颜色映射，增强可视化效果。
  6. 记录性能日志（目标、内存占用、模型大小、点数量、渲染时间、大小分布），输出到控制台。
  7. 在组件卸载时清理 VTK 资源，防止内存泄漏。

  代码结构：
  - **模板部分**：仅包含全屏渲染窗口，用于显示点云。
  - **脚本部分**：使用 Vue 3 的组合式 API（<script setup>），定义配置变量，初始化 VTK.js 渲染器，生成点云数据，渲染场景，记录日志。
  - **样式部分**：定义全屏布局样式，确保渲染窗口占满页面。

  注意事项：
  - 点数量由 cubeCountPerAxis 定义（n^3 点），较大值（如 n > 50）可能导致性能问题，建议根据硬件性能调整。
  - 随机大小模式下，sizeConfigs 的比例总和应接近 100%，代码会自动归一化。
  - 内存占用通过 performance.memory 估算，仅在支持该 API 的浏览器（如 Chrome）有效。
  - 日志输出到控制台，可扩展为保存到后端或显示在界面。
-->

<template>
  <div class="container">
    <!-- 渲染容器，用于承载 vtk.js 的全屏渲染窗口 -->
    <div ref="renderContainer" class="render-window"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue';

// 引入 vtk.js 相关模块
import '@kitware/vtk.js/Rendering/Profiles/Geometry';
import '@kitware/vtk.js/Rendering/Profiles/Glyph';
import vtkFullScreenRenderWindow from '@kitware/vtk.js/Rendering/Misc/FullScreenRenderWindow';
import vtkPolyData from '@kitware/vtk.js/Common/DataModel/PolyData';
import vtkPoints from '@kitware/vtk.js/Common/Core/Points';
import vtkCubeSource from '@kitware/vtk.js/Filters/Sources/CubeSource';
import vtkGlyph3DMapper from '@kitware/vtk.js/Rendering/Core/Glyph3DMapper';
import vtkActor from '@kitware/vtk.js/Rendering/Core/Actor';
import vtkColorTransferFunction from '@kitware/vtk.js/Rendering/Core/ColorTransferFunction';
import DataArray from '@kitware/vtk.js/Common/Core/DataArray';

// 配置变量（可直接修改）
const cubeCountPerAxis = 20; // 每轴点数，20^3 = 8000 点
const sizeMode = 'random'; // 大小模式：'uniform'（统一大小）或 'random'（随机大小）
const sizeConfigs = [
  { value: 0.5, ratio: 40 }, // 大小 1：0.5，比例 40%
  { value: 2.5, ratio: 40 }, // 大小 2：2.5，比例 40%
  { value: 5.0, ratio: 20 }, // 大小 3：5.0，比例 20%
];

// 响应式变量
const renderContainer = ref(null); // 渲染容器引用

// 全局渲染对象
let fullScreenRenderer, renderer, renderWindow;

// 组件挂载时初始化渲染器并渲染点云
onMounted(() => {
  // 初始化全屏渲染窗口
  fullScreenRenderer = vtkFullScreenRenderWindow.newInstance({
    rootContainer: renderContainer.value,
    background: [0.1, 0.1, 0.1], // 深灰色背景
  });
  renderer = fullScreenRenderer.getRenderer();
  renderWindow = fullScreenRenderer.getRenderWindow();

  // ======== 1. 生成规则网格点 ========
  // 记录开始时间
  const startTime = performance.now();

  const numPoints = cubeCountPerAxis ** 3; // 总点数
  const spacing = 12; // 点间距
  const coords = new Float32Array(numPoints * 3); // 点坐标数组
  const cubeSizes = new Float32Array(numPoints); // 立方体大小数组

  // 生成点坐标和大小
  let idx = 0;
  let totalRatio; // 定义 totalRatio 变量
  if (sizeMode === 'uniform') {
    // 统一大小
    const uniformSize = 2.0; // 默认统一大小为 2.0
    for (let x = 0; x < cubeCountPerAxis; x++) {
      for (let y = 0; y < cubeCountPerAxis; y++) {
        for (let z = 0; z < cubeCountPerAxis; z++) {
          coords[idx * 3] = x * spacing;
          coords[idx * 3 + 1] = y * spacing;
          coords[idx * 3 + 2] = z * spacing;
          cubeSizes[idx] = uniformSize;
          idx++;
        }
      }
    }
  } else {
    // 随机大小
    // 验证 sizeConfigs
    if (!sizeConfigs || sizeConfigs.length === 0) {
      console.error('sizeConfigs 为空或未定义！');
      return;
    }

    // 计算比例总和
    totalRatio = sizeConfigs.reduce((sum, config) => sum + (config.ratio || 0), 0);
    if (totalRatio <= 0) {
      console.error('sizeConfigs 的比例总和为 0！');
      return;
    }

    const normalizedRatios = sizeConfigs.map(config => config.ratio / totalRatio);
    const cumulativeRatios = normalizedRatios.reduce((acc, ratio, i) => {
      acc.push((acc[i - 1] || 0) + ratio);
      return acc;
    }, [0]);

    // 确保 cumulativeRatios 最后一个值接近 1
    cumulativeRatios[cumulativeRatios.length - 1] = 1.0; // 强制校正最后一个值为 1

    for (let x = 0; x < cubeCountPerAxis; x++) {
      for (let y = 0; y < cubeCountPerAxis; y++) {
        for (let z = 0; z < cubeCountPerAxis; z++) {
          coords[idx * 3] = x * spacing;
          coords[idx * 3 + 1] = y * spacing;
          coords[idx * 3 + 2] = z * spacing;
          // 根据比例随机选择大小
          const rand = Math.random();
          const sizeIndex = cumulativeRatios.findIndex(r => rand < r);
          // 防御性检查
          if (sizeIndex === -1 || sizeIndex >= sizeConfigs.length) {
            console.warn(`无效的 sizeIndex: ${sizeIndex}, 使用默认大小`);
            cubeSizes[idx] = sizeConfigs[0].value; // 回退到第一个大小
          } else {
            cubeSizes[idx] = sizeConfigs[sizeIndex].value;
          }
          idx++;
        }
      }
    }
  }

  // ======== 2. 创建 PolyData ========
  const points = vtkPoints.newInstance();
  points.setData(coords, 3); // 每个点 3 个分量 (x, y, z)
  const polyData = vtkPolyData.newInstance();
  polyData.setPoints(points);
  polyData.getPointData().addArray(
    DataArray.newInstance({
      name: 'CubeSize',
      values: cubeSizes,
    })
  );

  // ======== 3. 颜色映射 ========
  const lut = vtkColorTransferFunction.newInstance();
  const minSize = sizeMode === 'uniform' ? 2.0 : Math.min(...sizeConfigs.map(c => c.value || 2.0));
  const maxSize = sizeMode === 'uniform' ? 2.0 : Math.max(...sizeConfigs.map(c => c.value || 2.0));
  lut.addRGBPoint(minSize, 0.2, 0.2, 1.0); // 蓝色
  lut.addRGBPoint((minSize + maxSize) / 2, 0.2, 1.0, 0.2); // 绿色
  lut.addRGBPoint(maxSize, 1.0, 0.2, 0.2); // 红色

  // ======== 4. 创建立方体源 ========
  const cubeSource = vtkCubeSource.newInstance({
    xLength: 1,
    yLength: 1,
    zLength: 1,
  });

  // ======== 5. 创建 Glyph3DMapper ========
  const mapper = vtkGlyph3DMapper.newInstance();
  mapper.setInputData(polyData);
  mapper.setSourceConnection(cubeSource.getOutputPort());
  mapper.setScaling(true);
  mapper.setScaleArray('CubeSize');
  mapper.setScaleFactor(1.0);
  mapper.setScalarVisibility(true);
  mapper.setScalarModeToUsePointData();
  mapper.setLookupTable(lut);
  mapper.setScalarRange(minSize, maxSize);

  // ======== 6. 创建 Actor 并渲染 ========
  const actor = vtkActor.newInstance();
  actor.setMapper(mapper);
  renderer.addActor(actor);

  // 重置相机并渲染
  renderer.resetCamera();
  renderWindow.render();

  // ======== 7. 记录性能日志 ========
  const endTime = performance.now();
  const renderTime = endTime - startTime; // 渲染耗时（ms）
  const modelSize = (coords.byteLength + cubeSizes.byteLength) / 1024 / 1024; // 模型大小（MB）
  const memoryUsed = window.performance.memory
    ? (window.performance.memory.usedJSHeapSize / 1024 / 1024).toFixed(2) // 内存占用（MB）
    : '不可用（浏览器不支持 performance.memory）';

  // 生成大小分布日志
  const sizeDistribution = sizeMode === 'uniform'
    ? '统一大小: 2.0'
    : sizeConfigs.map((config, i) => `大小 ${i + 1}: ${config.value}, 比例: ${((config.ratio / (totalRatio || 1)) * 100).toFixed(2)}%`).join('\n');

  // 输出日志到控制台
  console.log(`
测试目标: ${sizeMode === 'uniform' ? '统一大小立方体点云' : '随机大小立方体点云'}
点数量: ${numPoints}
内存占用: ${memoryUsed} MB
模型大小: ${modelSize.toFixed(2)} MB
渲染时间: ${renderTime.toFixed(2)} ms
立方体大小分布:
${sizeDistribution}
  `.trim());
});

// 组件卸载时清理资源
onUnmounted(() => {
  // 说明：vtk.js 的对象需要手动清理以释放内存
  if (fullScreenRenderer) {
    fullScreenRenderer.delete(); // 释放 VTK 资源
  }
});
</script>

<style scoped>
.container {
  width: 100%; /* 容器宽度占满父元素 */
  height: 100vh; /* 容器高度占满视口 */
}
.render-window {
  width: 100%; /* 渲染窗口宽度占满容器 */
  height: 100%; /* 渲染窗口高度占满容器 */
}
</style>