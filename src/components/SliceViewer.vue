<template>
    <div class="viewer">
      <div ref="vtkContainer" class="vtk-container"></div>
  
      <div class="controls">
        <label>
          切片方向：
          <select v-model="activeAxis" @change="onAxisChange">
            <option value="X">X</option>
            <option value="Y">Y</option>
            <option value="Z">Z</option>
          </select>
        </label>
  
        <label>
          切片索引：
          <input type="range" :min="0" :max="maxSlice" v-model="sliceIndex" @input="updateSlice" />
          {{ sliceIndex }}
        </label>
  
        <label>
          多轴模式：
          <input type="checkbox" v-model="multiAxisMode" @change="updateMultiMode" />
        </label>
      </div>
    </div>
  </template>
  
  <script setup>
  import { ref, onMounted, watch } from 'vue'
  import vtkFullScreenRenderWindow from '@kitware/vtk.js/Rendering/Misc/FullScreenRenderWindow'
  import vtkImageSlice from '@kitware/vtk.js/Rendering/Core/ImageSlice'
  
  const vtkContainer = ref(null)
  const activeAxis = ref('Z')
  const sliceIndex = ref(0)
  const maxSlice = ref(0)
  const multiAxisMode = ref(false)
  
  let mapper, actor, renderer, renderWindow, imageData
  
  onMounted(async () => {
    const fullScreenRenderer = vtkFullScreenRenderWindow.newInstance({
      rootContainer: vtkContainer.value,
      containerStyle: { height: '500px', width: '100%' },
    })
    renderer = fullScreenRenderer.getRenderer()
    renderWindow = fullScreenRenderer.getRenderWindow()
    
    // 读取 .vti 文件
    const response = await fetch('/SaltfFF.vti'); // 确保文件在 public 目录
    const arrayBuffer = await response.arrayBuffer();

    const reader = vtkImageSlice.newInstance();
    reader.parseAsArrayBuffer(arrayBuffer);
    imageData = reader.getOutputData()
  
    mapper = vtkMultiSliceImageMapper.newInstance()
    actor = vtkImageSlice.newInstance()
  
    mapper.setInputData(imageData)
    actor.setMapper(mapper)
  
    renderer.addViewProp(actor)
    renderer.resetCamera()
    renderWindow.render()
  
    initSlice()
  })
  
  function initSlice() {
    const dims = imageData.getDimensions()
    maxSlice.value = {
      X: dims[0] - 1,
      Y: dims[1] - 1,
      Z: dims[2] - 1,
    }[activeAxis.value]
  
    updateSlice()
  }
  
  function updateSlice() {
    const axisMap = { X: 0, Y: 1, Z: 2 }
  
    mapper.removeAllSlices()
  
    if (multiAxisMode.value) {
      // 同时显示三个方向
      mapper.addSlice(0, Math.floor(imageData.getDimensions()[0] / 2))
      mapper.addSlice(1, Math.floor(imageData.getDimensions()[1] / 2))
      mapper.addSlice(2, Math.floor(imageData.getDimensions()[2] / 2))
    } else {
      mapper.addSlice(axisMap[activeAxis.value], Number(sliceIndex.value))
    }
  
    renderWindow.render()
  }
  
  function onAxisChange() {
    initSlice()
  }
  
  function updateMultiMode() {
    updateSlice()
  }
  </script>
  
  <style scoped>
  .viewer {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }
  .vtk-container {
    border: 1px solid #ccc;
  }
  .controls {
    display: flex;
    gap: 1rem;
    flex-wrap: wrap;
    align-items: center;
  }
  </style>
  