<!-- 
  代码功能说明：
  本组件基于 Vue 3 和 VTK.js，实现从自定义二进制点八叉树数据格式（point_octree.bin）中解析点数据并进行点云渲染。
  数据通过递归方式从二进制文件中解析为离散的三维采样点坐标和标量值，使用颜色映射进行可视化。
  应用适用于自定义点数据的渲染调试场景，并使用全屏渲染器和离屏缓冲提升渲染效率。

  基本流程：
  1. 初始化 VTK.js 全屏渲染窗口，挂载到容器并设置黑色背景。
  2. 通过 fetch 加载二进制点八叉树数据（point_octree.bin），递归解码为采样点数组。
  3. 构建 vtkPolyData 容器封装点数据，设置坐标数组和标量数组。
  4. 创建渲染管线（Mapper + Actor），配置点渲染属性和颜色映射。
  5. 定义颜色传输函数，实现标量值视觉映射。
  6. 渲染器添加点云对象，重置相机并执行初始渲染。
-->

<template>
  <!-- 渲染容器，用于挂载 VTK 的 WebGL 渲染窗口 -->
  <div ref="container" class="vtk-container"></div>
</template>

<script setup>
import { onMounted, ref } from 'vue';

import '@kitware/vtk.js/favicon';
import '@kitware/vtk.js/Rendering/Profiles/Geometry'; // 加载几何渲染功能集

import vtkFullScreenRenderWindow from '@kitware/vtk.js/Rendering/Misc/FullScreenRenderWindow'; // 创建全屏渲染窗口
import vtkActor from '@kitware/vtk.js/Rendering/Core/Actor'; // VTK 渲染对象
import vtkMapper from '@kitware/vtk.js/Rendering/Core/SphereMapper'; // 映射几何数据到图像
import vtkPolyData from '@kitware/vtk.js/Common/DataModel/PolyData'; // 多边形数据容器（用于点云）
import vtkPoints from '@kitware/vtk.js/Common/Core/Points'; // 点坐标数据结构
import vtkDataArray from '@kitware/vtk.js/Common/Core/DataArray'; // 数据数组封装标量值
import vtkColorTransferFunction from '@kitware/vtk.js/Rendering/Core/ColorTransferFunction'; // 颜色映射函数
import vtkLookupTable from '@kitware/vtk.js/Common/Core/LookupTable'; // 查找表用于颜色映射

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

  const t0 = performance.now(); // ⏱️ 开始计时（加载模型）
  
  // 加载自定义 point_octree.bin 数据文件
  fetch('/point_octree.bin')
    .then(response => response.arrayBuffer())
    .then(arrayBuffer => {
      const t1 = performance.now(); // ⏱️ 加载完成
      console.log(`📦 模型加载时间（fetch + arrayBuffer）: ${(t1 - t0).toFixed(2)} ms`);

      const t2 = performance.now(); // ⏱️ 开始构建八叉树
      const view = new DataView(arrayBuffer);

      // 读取点数据的维度信息 nx × ny × nz
      let pos = 0;
      const nx = view.getUint32(pos, true); pos += 4;
      const ny = view.getUint32(pos, true); pos += 4;
      const nz = view.getUint32(pos, true); pos += 4;

      // 递归解析八叉树采样点节点
      const points = [];
      
      const parseNode = () => {
        const byte = view.getUint8(pos); pos++;
        if (byte === 0) {
          // 叶子节点：读取采样点坐标和值
          const value = view.getFloat32(pos, true); pos += 4;
          const x = view.getFloat32(pos, true); pos += 4;
          const y = view.getFloat32(pos, true); pos += 4;
          const z = view.getFloat32(pos, true); pos += 4;
          points.push([x, y, z, value]);
        } else {
          // 内部节点：递归解析 8 个子节点
          for (let i = 0; i < 8; i++) {
            parseNode();
          }
        }
      };

      // 启动八叉树解析
      parseNode();

      const t3 = performance.now(); // ⏱️ 构建完成
      console.log(`🌲 八叉树构建时间（解析点数组）: ${(t3 - t2).toFixed(2)} ms`);

      const numberOfPoints = points.length;
      console.log(`🔵 点数量: ${numberOfPoints} 个`);

      // 打印当前页面内存使用情况
      if (performance.memory) {
        const used = (performance.memory.usedJSHeapSize / 1024 / 1024).toFixed(2);
        const total = (performance.memory.totalJSHeapSize / 1024 / 1024).toFixed(2);
        const limit = (performance.memory.jsHeapSizeLimit / 1024 / 1024).toFixed(2);
        console.log(`💾 内存使用: 已用 ${used} MB / 分配 ${total} MB / 限制 ${limit} MB`);
      } else {
        console.warn('⚠️ 当前浏览器不支持 performance.memory');
      }

      // 创建点坐标和标量数据数组
      const pointsArray = new Float32Array(numberOfPoints * 3);
      const scalarsArray = new Float32Array(numberOfPoints);
      
      for (let i = 0; i < numberOfPoints; i++) {
        const point = points[i];
        const idx = i * 3;
        pointsArray[idx] = point[0];     // x
        pointsArray[idx + 1] = point[1]; // y
        pointsArray[idx + 2] = point[2]; // z
        scalarsArray[i] = point[3];      // value
      }

      // 创建 vtkPolyData 对象并设置基础属性
      const polyData = vtkPolyData.newInstance();
      
      // 封装点坐标为 VTK Points 对象
      const vtkPointsInstance = vtkPoints.newInstance({ numberOfPoints });
      vtkPointsInstance.setData(pointsArray);
      polyData.setPoints(vtkPointsInstance);

      // 封装标量数据为 VTK 数据数组，并绑定到 polyData
      const scalars = vtkDataArray.newInstance({
        name: 'scalars',
        values: scalarsArray,
        numberOfComponents: 1,
      });
      polyData.getPointData().setScalars(scalars);

      // 获取标量值范围（用于颜色映射）
      const dataRange = scalars.getRange();

      // 创建点云渲染对象和 Mapper，并绑定数据
      const actor = vtkActor.newInstance();
      const mapper = vtkMapper.newInstance();
      mapper.setRadius(2.0); // 设置球体大小
      mapper.setInputData(polyData);

      // 配置点渲染属性
      actor.setMapper(mapper);
      actor.getProperty().setPointSize(3.0);
      actor.getProperty().setOpacity(0.8);

      // 创建颜色映射函数（蓝 → 绿 → 红）
      const ctfun = vtkColorTransferFunction.newInstance();
      ctfun.addRGBPoint(dataRange[0], 0.0, 0.0, 1.0); // 最低值为蓝色
      ctfun.addRGBPoint((dataRange[0] + dataRange[1]) / 2, 0.0, 1.0, 0.0); // 中值为绿色
      ctfun.addRGBPoint(dataRange[1], 1.0, 0.0, 0.0); // 最高值为红色

      // 创建查找表用于颜色映射
      const lookupTable = vtkLookupTable.newInstance();
      const numberOfColors = 256;
      const rgbArray = new Uint8Array(numberOfColors * 4);
      const rgb = [];

      for (let i = 0; i < numberOfColors; i++) {
        const normalizedValue = dataRange[0] + (dataRange[1] - dataRange[0]) * (i / (numberOfColors - 1));
        ctfun.getColor(normalizedValue, rgb);
        const idx = i * 3;
        rgbArray[idx] = rgb[0];
        rgbArray[idx + 1] = rgb[1];
        rgbArray[idx + 2] = rgb[2];
        rgbArray[idx + 3] = rgb[3]; // alpha
      }

      const vtkColorTable = vtkDataArray.newInstance({
        numberOfComponents: 4,
        values: rgbArray,
        dataType: 'Uint8Array',
      });

      lookupTable.setNumberOfColors(numberOfColors);
      lookupTable.setRange(dataRange[0], dataRange[1]);
      lookupTable.setTable(vtkColorTable); // ✅ 正确方式

      // 配置 mapper 的颜色映射
      // mapper.setLookupTable(lookupTable);
      mapper.setScalarRange(dataRange[0], dataRange[1]);

      // 添加点云对象到渲染器，重置相机并渲染
      renderer.addActor(actor);
      renderer.resetCamera();
      renderWindow.render();

      const t4 = performance.now(); // ⏱️ 渲染完成
      console.log(`🖼️ 渲染阶段耗时（构建完成 → 画面显示）: ${(t4 - t3).toFixed(2)} ms`);
      console.log(`⏱️ 总耗时（从 fetch 开始 → 渲染完成）: ${(t4 - t0).toFixed(2)} ms`);

      // 清理临时对象
      scalars.delete();
      ctfun.delete();
      lookupTable.delete();
    })
    .catch(error => {
      console.error('加载点八叉树数据失败:', error);
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
