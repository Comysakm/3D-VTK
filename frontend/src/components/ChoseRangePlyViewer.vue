<template>
  <div class="container">
    <div ref="renderContainer" class="render-window"></div>

    <div class="control">
      <h3>Point Cloud Filter</h3>
      <div class="input-group">
        <label>Minimum Value: </label>
        <input v-model.number="minValue" type="number" placeholder="e.g., 1500" />
      </div>
      <div class="input-group">
        <label>Maximum Value: </label>
        <input v-model.number="maxValue" type="number" placeholder="e.g., 4500" />
      </div>
      <button :disabled="loading" @click="fetchPlyFile">Generate and Render</button>
      <p v-if="loading">Loading... ({{ progress }}%)</p>
      <p v-if="error" class="error">{{ error }}</p>
      <p v-if="fileInfo">File Size: {{ fileInfo.size }} MB, Points: {{ fileInfo.points }}</p>
    </div>

    <div class="coordinate-display" id="coordinate-display"></div>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue';
import axios from 'axios';
import '@kitware/vtk.js/Rendering/Profiles/Geometry';
import vtkFullScreenRenderWindow from '@kitware/vtk.js/Rendering/Misc/FullScreenRenderWindow';
import vtkPLYReader from '@kitware/vtk.js/IO/Geometry/PLYReader';
import vtkActor from '@kitware/vtk.js/Rendering/Core/Actor';
import vtkCubeSource from '@kitware/vtk.js/Filters/Sources/CubeSource';
import vtkGlyph3DMapper from '@kitware/vtk.js/Rendering/Core/Glyph3DMapper';
import vtkColorTransferFunction from '@kitware/vtk.js/Rendering/Core/ColorTransferFunction';
import vtkCellPicker from '@kitware/vtk.js/Rendering/Core/CellPicker';
import '@kitware/vtk.js/Rendering/Profiles/Glyph';

const minValue = ref(1500);
const maxValue = ref(4500);
const loading = ref(false);
const progress = ref(0);
const error = ref('');
const fileInfo = ref(null);
const renderContainer = ref(null);

// 修改1: 添加对当前点云数据的引用
const currentPolyData = ref(null);
let fullScreenRenderer, renderer, renderWindow, picker;

onMounted(() => {
  console.log('Initializing vtk.js renderer...');
  fullScreenRenderer = vtkFullScreenRenderWindow.newInstance({
    rootContainer: renderContainer.value,
    background: [0, 0, 0],
  });
  renderer = fullScreenRenderer.getRenderer();
  renderWindow = fullScreenRenderer.getRenderWindow();

  const interactor = renderWindow.getInteractor();
  
  // 修改2: 创建并复用拾取器实例
  picker = vtkCellPicker.newInstance();
  picker.setTolerance(0.001);
  
  interactor.onMouseMove((event) => {
    const mousePos = interactor.getEventPosition();
    picker.pick(mousePos[0], mousePos[1], 0, renderer);

    const pickedPosition = picker.getPickPosition();
    const cellId = picker.getCellId();
    
    // 修改3: 使用原始点云数据获取坐标
    if (cellId !== -1 && currentPolyData.value) {
      const points = currentPolyData.value.getPoints();
      const point = points.getPoint(cellId);
      if (point) {
        const [x, y, z] = point;
        document.getElementById('coordinate-display').innerText = 
          `X: ${x.toFixed(2)}, Y: ${y.toFixed(2)}, Z: ${z.toFixed(2)}`;
      }
    } else if (pickedPosition) {
      const [x, y, z] = pickedPosition;
      document.getElementById('coordinate-display').innerText = 
        `X: ${x.toFixed(2)}, Y: ${y.toFixed(2)}, Z: ${z.toFixed(2)}`;
    }
  });
});

onUnmounted(() => {
  if (fullScreenRenderer) {
    fullScreenRenderer.delete();
  }
});

async function fetchPlyFile() {
  const now = new Date();
  const timeMs = now.toISOString().split('T')[1].replace('z', '');
  console.log("提交范围时间", timeMs);

  if (!minValue.value || !maxValue.value || minValue.value >= maxValue.value) {
    error.value = 'Please enter valid min and max values (min < max).';
    return;
  }

  loading.value = true;
  progress.value = 0;
  error.value = '';
  fileInfo.value = null;
  renderer.removeAllActors();
  // 重置点云引用
  currentPolyData.value = null;

  try {
    const response = await axios.post(
      'http://localhost:5000/generate-ply',
      { min_val: minValue.value, max_val: maxValue.value },
      {
        responseType: 'arraybuffer',
        onDownloadProgress: (progressEvent) => {
          if (progressEvent.total) {
            progress.value = Math.round((progressEvent.loaded / progressEvent.total) * 100);
          }
        },
      }
    );

    const arrayBuffer = response.data;
    const fileSizeMB = (arrayBuffer.byteLength / (1024 * 1024)).toFixed(2);
    console.log(`Received PLY file, size: ${fileSizeMB} MB`);

    const reader = vtkPLYReader.newInstance();
    console.time('parse_ply');
    reader.parseAsArrayBuffer(arrayBuffer);
    console.timeEnd('parse_ply');

    const polyData = reader.getOutputData();
    // 保存点云数据用于拾取
    currentPolyData.value = polyData;
    
    const numPoints = polyData.getPoints()?.getNumberOfValues() / 3 || 0;
    console.log(`Number of Points: ${numPoints}`);
    console.log(`Bounds:`, polyData.getBounds());

    const pointData = polyData.getPointData();
    const scalars = pointData.getArrayByName('scalar') || pointData.getArrayByName('volume') || pointData.getScalars();
    
    if (scalars) {
      console.log('Scalar Array Name:', scalars.getName());
      console.log('Scalar Range:', scalars.getRange());
    } else {
      console.warn('No scalar data, using default color');
    }

    fileInfo.value = { size: fileSizeMB, points: numPoints };

    // 修改4: 使用Glyph3DMapper和CubeSource
    // 创建立方体源（默认尺寸1×1×1）
    const cubeSource = vtkCubeSource.newInstance();
    
    // 创建Glyph3D映射器
    const glyphMapper = vtkGlyph3DMapper.newInstance();
    glyphMapper.setInputData(polyData);
    glyphMapper.setSourceConnection(cubeSource.getOutputPort());
    
    // 设置立方体大小（20×20×20）
    glyphMapper.setScaleFactor(20);
    
    // 优化性能设置
    glyphMapper.setOrient(false);       // 不需要方向
    glyphMapper.setScaling(true);       // 启用缩放
    glyphMapper.setScaleModeToScaleByMagnitude(); // 使用统一缩放
    
    // 创建Actor
    const actor = vtkActor.newInstance();
    actor.setMapper(glyphMapper);
    
    // 设置颜色映射
    if (scalars) {
      glyphMapper.setScalarVisibility(true);
      glyphMapper.setScalarModeToUsePointData();
      
      const lut = vtkColorTransferFunction.newInstance();
      const scalarRange = scalars.getRange();
      lut.addRGBPoint(scalarRange[0], 0, 0, 1);
      lut.addRGBPoint((scalarRange[0] + scalarRange[1]) / 2, 0, 1, 0);
      lut.addRGBPoint(scalarRange[1], 1, 0, 0);
      
      glyphMapper.setLookupTable(lut);
      glyphMapper.setScalarRange(scalarRange[0], scalarRange[1]);
    } else {
      actor.getProperty().setColor(128, 128, 128);
    }
    
    // 设置立方体边缘可见（可选）
    actor.getProperty().setEdgeVisibility(true);
    actor.getProperty().setEdgeColor(0.2, 0.2, 0.2);
    actor.getProperty().setPointSize(0); // 隐藏原始点

    renderer.addActor(actor);
    renderer.resetCamera();
    console.log('Starting render...');
    renderWindow.render();
    
    const endTime = new Date();
    const endTimeMs = endTime.toISOString().split('T')[1].replace('z', '');
    console.log("渲染成功时间", endTimeMs);
    console.log('Render complete.');
  } catch (err) {
    error.value = `Error: ${err.message}`;
    console.error('Error fetching or rendering PLY:', err);
  } finally {
    loading.value = false;
    progress.value = 0;
  }
}
</script>

<style scoped>
.container {
  display: flex;
  flex-direction: row;
  height: 100vh;
  position: relative;
}

.render-window {
  flex: 1;
  background: black;
  position: relative;
  z-index: 1;
}

.control {
  width: 250px;
  padding: 1rem;
  background-color: #f4f4f4;
  font-family: sans-serif;
  overflow-y: auto;
  z-index: 2;
  position: relative;
}

.control h3 {
  margin-bottom: 1rem;
}

.input-group {
  margin: 10px 0;
}

.input-group label {
  margin-right: 10px;
}

input {
  padding: 5px;
  width: 100px;
}

button {
  padding: 8px 16px;
  background: #007bff;
  color: white;
  border: none;
  cursor: pointer;
}

button:disabled {
  background: #6c757d;
  cursor: not-allowed;
}

.error {
  color: red;
}

.coordinate-display {
  position: absolute;
  top: 20px;
  left: 20px;
  color: white;
  font-size: 14px;
  background-color: rgba(0, 0, 0, 0.6);
  padding: 5px;
  border-radius: 5px;
  z-index: 3;
}
</style>