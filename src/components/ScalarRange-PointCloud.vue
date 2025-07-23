<!-- 
  代码功能说明：
  这是一个基于 Vue 3 和 VTK.js 的点云渲染应用，用于从 VTI 格式的体视显微镜数据中提取点云并进行渲染。
  用户可以通过滑块调整最小值（min）来过滤点云数据，并通过下拉菜单选择渲染模式（点云或球体）。
  应用会根据用户设置的最小值范围提取点云数据，并支持两种渲染方式：基础点云（basic）或球体（glyph）。

  基本流程：
  1. 初始化 VTK.js 渲染器，设置全屏渲染窗口和黑色背景。
  2. 使用 fetch 加载 VTI 文件，解析体视显微镜数据。
  3. 计算体数据的标量范围，设置滑块的范围和初始值。
  4. 根据用户设置的最小值和固定范围（min + 50）提取点云数据。
  5. 根据选择的渲染模式（basic 或 glyph）配置 VTK 渲染管线（Mapper 和 Actor）。
  6. 动态更新点云并重新渲染，支持相机自动调整。
-->

<template>
  <!-- 主容器，包含渲染窗口和控制面板 -->
  <div class="viewer-container">
    <!-- VTK 渲染窗口，用于显示点云 -->
    <div ref="vtkContainer" class="vtk-container"></div>

    <!-- 控制面板，包含最小值滑块和渲染模式选择 -->
    <div class="controls">
      <!-- 最小值滑块，用于过滤点云数据 -->
      <div>
        <label>Min: {{ min }}</label>
        <input
          type="range"
          v-model="min"
          :min="minRange"
          :max="maxRange"
          :step="step"
          @input="updatePointCloud"
        />
      </div>

      <!-- 渲染模式选择下拉菜单 -->
      <div>
        <label>Render Mode: </label>
        <select v-model="renderMode" @change="updatePointCloud">
          <option value="basic">点云（轻量）</option>
          <option value="glyph">点云（球体）</option>
        </select>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue';
import vtkFullScreenRenderWindow from '@kitware/vtk.js/Rendering/Misc/FullScreenRenderWindow'; // 用于创建全屏渲染窗口
import vtkActor from '@kitware/vtk.js/Rendering/Core/Actor'; // VTK 渲染对象
import vtkMapper from '@kitware/vtk.js/Rendering/Core/Mapper'; // 用于映射几何数据到渲染对象（基础点云）
import vtkGlyph3DMapper from '@kitware/vtk.js/Rendering/Core/Glyph3DMapper'; // 用于映射球体点云
import vtkSphereSource from '@kitware/vtk.js/Filters/Sources/SphereSource'; // 用于生成球体几何
import vtkXMLImageDataReader from '@kitware/vtk.js/IO/XML/XMLImageDataReader'; // 用于解析 VTI 文件
import vtkDataArray from '@kitware/vtk.js/Common/Core/DataArray'; // 用于创建标量数据数组
import vtkPolyData from '@kitware/vtk.js/Common/DataModel/PolyData'; // 用于创建点云数据
import vtkPoints from '@kitware/vtk.js/Common/Core/Points'; // 用于存储点坐标

// 定义响应式变量
const vtkContainer = ref(null); // 绑定 HTML 渲染容器
const min = ref(0); // 最小值，控制点云过滤范围
const max = ref(0); // 最大值（固定为 min + 50）
const renderMode = ref('basic'); // 渲染模式，默认为基础点云
const minRange = ref(0); // 滑块最小范围
const maxRange = ref(0); // 滑块最大范围
const step = ref(1); // 滑块步长

// 定义 VTK 对象引用
let renderer, renderWindow, actor, imageData;
let sphereSource, glyphMapper, basicMapper;

// 提取点云数据的函数
function extractPointCloud(imageData, minValue, maxValue) {
  console.log('提取点云数据...');
  // 获取体数据的维度、原点和间距
  const dims = imageData.getDimensions();
  const origin = imageData.getOrigin();
  const spacing = imageData.getSpacing();
  const scalars = imageData.getPointData().getScalars();
  const values = scalars.getData();

  // 初始化点坐标和标量值数组
  const points = [];
  const scalarValues = [];

  // 遍历体数据的每个体素，提取满足范围条件的点
  for (let z = 0; z < dims[2]; z++) {
    for (let y = 0; y < dims[1]; y++) {
      for (let x = 0; x < dims[0]; x++) {
        const idx = x + y * dims[0] + z * dims[0] * dims[1];
        const val = values[idx];
        // 如果体素值在指定范围内，添加点坐标和标量值
        if (val >= minValue && val <= maxValue) {
          points.push(
            origin[0] + x * spacing[0],
            origin[1] + y * spacing[1],
            origin[2] + z * spacing[2]
          );
          scalarValues.push(val);
        }
      }
    }
  }

  // 提示提取完成并显示点数
  alert("提取点云数据完成，点数：" + points.length / 3);
  console.log('前几个点坐标:', points.slice(0, 12)); // 输出前 4 个点的坐标
  console.log('前几个标量值:', scalarValues.slice(0, 4));

  // 创建点云数据对象
  const polyData = vtkPolyData.newInstance();
  const vtkPointsData = vtkPoints.newInstance();
  vtkPointsData.setData(new Float32Array(points), 3); // 设置点坐标
  polyData.setPoints(vtkPointsData);

  // 创建标量数据数组
  const vtkScalars = vtkDataArray.newInstance({
    name: 'FilteredScalars',
    values: new Float32Array(scalarValues),
    numberOfComponents: 1,
  });
  polyData.getPointData().setScalars(vtkScalars);

  console.log(`点云数据提取完成，点数: ${points.length / 3}`);
  return polyData;
}

// 更新点云的函数
function updatePointCloud() {
  // 检查体数据是否已加载
  if (!imageData) return;
  console.log('更新点云数据...');

  // 验证最小值是否在合法范围内
  if (min.value >= maxRange.value - 50 || min.value < minRange.value) {
    alert("选值范围不合法，请重新选择！");
    min.value = minRange.value;
    return;
  }

  // 提取点云数据，最大值为 min + 50
  const polyData = extractPointCloud(imageData, min.value, min.value + 50);

  if (renderMode.value === 'glyph') {
    // 使用 glyph 模式渲染球体点云
    if (!sphereSource) {
      // 根据体数据的间距动态调整球体半径
      const spacing = imageData.getSpacing();
      const radius = Math.min(spacing[0], spacing[1], spacing[2]) * 0.5;
      sphereSource = vtkSphereSource.newInstance({
        radius,
        thetaResolution: 16,
        phiResolution: 16,
      });
    }
    if (!glyphMapper) {
      // 创建并配置 Glyph3DMapper
      glyphMapper = vtkGlyph3DMapper.newInstance();
      glyphMapper.setScalarVisibility(true); // 启用标量可视化
      glyphMapper.setColorModeToDefault(); // 使用默认颜色模式
      glyphMapper.setScaleFactor(1.0); // 设置缩放因子
      glyphMapper.setScaleModeToDataScalingOff(); // 禁用数据缩放
    }
    glyphMapper.setInputData(polyData); // 设置点云数据
    glyphMapper.setGlyphSource(sphereSource.getOutputData()); // 设置球体几何
    actor.setMapper(glyphMapper); // 为 Actor 设置 Glyph 映射器
  } else {
    // 使用基础模式渲染点云
    if (!basicMapper) {
      basicMapper = vtkMapper.newInstance();
    }
    basicMapper.setInputData(polyData); // 设置点云数据
    actor.setMapper(basicMapper); // 为 Actor 设置基础映射器
    actor.getProperty().setPointSize(10); // 设置点大小为 10
  }

  // 触发场景重新渲染
  renderWindow.render();
  console.log('点云更新完成');
}

// 计算体数据标量范围的函数
function computeRange(values) {
  let min = Infinity;
  let max = -Infinity;
  // 遍历标量值，计算最小值和最大值
  for (let i = 0; i < values.length; i++) {
    const v = values[i];
    if (v < min) min = v;
    if (v > max) max = v;
  }
  return { min, max };
}

// 组件挂载时执行的初始化逻辑
onMounted(async () => {
  // 初始化 VTK 全屏渲染窗口，设置容器和样式
  const fullScreenRenderer = vtkFullScreenRenderWindow.newInstance({
    rootContainer: vtkContainer.value,
    containerStyle: { height: '100%', width: '100%' },
  });

  // 获取渲染器和渲染窗口
  renderer = fullScreenRenderer.getRenderer();
  renderWindow = fullScreenRenderer.getRenderWindow();

  // 创建并添加 Actor 到渲染器
  actor = vtkActor.newInstance();
  renderer.addActor(actor);

  // 使用 fetch 加载 VTI 文件
  const response = await fetch('/SaltfFF.vti'); // 确保路径正确
  const arrayBuffer = await response.arrayBuffer(); // 获取文件数据的 ArrayBuffer

  // 创建 VTI 文件解析器并解析数据
  const reader = vtkXMLImageDataReader.newInstance();
  reader.parseAsArrayBuffer(arrayBuffer);
  imageData = reader.getOutputData(0); // 获取解析后的体数据

  // 计算体数据的标量范围并设置滑块范围
  console.log("计算数据范围开始");
  const scalars = imageData.getPointData().getScalars();
  const values = scalars.getData();
  const { min: dataMin, max: dataMax } = computeRange(values);
  minRange.value = dataMin;
  maxRange.value = dataMax;
  min.value = dataMin;
  max.value = dataMin + 50;
  console.log("计算数据范围结束");

  // 初始化点云渲染
  console.log("开始");
  updatePointCloud();
  // 重置相机以适应渲染内容
  renderer.resetCamera();
  // 触发初始渲染
  renderWindow.render();
});
</script>

<style scoped>
/* 主容器样式，设置为纵向 flex 布局，占满视口高度 */
.viewer-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
}

/* 渲染窗口样式，占满剩余空间，背景为黑色 */
.vtk-container {
  flex: 1;
  background: black;
  height: 100%;
}

/* 控制面板样式，设置浅灰色背景，包含滑块和下拉菜单 */
.controls {
  padding: 10px;
  background-color: #f0f0f0;
  display: flex;
  flex-direction: row;
  justify-content: space-between;
  align-items: center;
}

/* 控制面板子容器样式，设置 flex 布局以对齐内容 */
.controls div {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

/* 滑块样式，设置宽度为 100% */
input[type="range"] {
  width: 100%;
}
</style>