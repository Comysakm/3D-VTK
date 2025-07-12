<template>
  <div class="viewer-wrapper">
    <!-- VTK 渲染窗口 -->
    <div ref="vtkContainer" class="vtk-viewer-container"></div>

    <!-- 控制面板：用于调节等值面值 -->
    <div class="control-panel">
      <label>
        等值面值 (contourValue): {{ contourValue }}
        <input
          type="range"
          min="1500"
          max="4482"
          step="1"
          v-model.number="contourValue"
          @input="updateContourValue"
        />
      </label>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'


import '@kitware/vtk.js/Rendering/Profiles/Geometry'
import vtkFullScreenRenderWindow from '@kitware/vtk.js/Rendering/Misc/FullScreenRenderWindow'
import vtkXMLImageDataReader from '@kitware/vtk.js/IO/XML/XMLImageDataReader' 
import vtkImageMarchingCubes from '@kitware/vtk.js/Filters/General/ImageMarchingCubes'
import vtkMapper from '@kitware/vtk.js/Rendering/Core/Mapper'
import vtkActor from '@kitware/vtk.js/Rendering/Core/Actor'

// 定义响应式变量和容器引用
const vtkContainer = ref(null)
const contourValue = ref(4482) // 当前等值面值（滑块控制）

// 这些是用于后续更新或渲染使用的 vtk 对象引用
let marchingCubes, renderWindow, mapper

onMounted(async () => {
  // 初始化全屏 vtk 渲染窗口
  const fullScreenRenderer = vtkFullScreenRenderWindow.newInstance({
    rootContainer: vtkContainer.value,
    containerStyle: { height: '100%', width: '100%', position: 'relative' },
  })
  const renderer = fullScreenRenderer.getRenderer()
  renderWindow = fullScreenRenderer.getRenderWindow()

  // 通过 fetch 加载 .vti 文件
  const response = await fetch('/SaltfFF.vti')
  const arrayBuffer = await response.arrayBuffer()

  // 解析 VTI 数据
  const reader = vtkXMLImageDataReader.newInstance()
  reader.parseAsArrayBuffer(arrayBuffer)

  // 创建 Marching Cubes 实例用于提取等值面
  marchingCubes = vtkImageMarchingCubes.newInstance({
    contourValue: contourValue.value, // 初始等值面值
  })

  // 将数据连接到算法处理流程中
  marchingCubes.setInputConnection(reader.getOutputPort())

  // 映射处理结果（polydata）到渲染管线
  mapper = vtkMapper.newInstance()
  mapper.setInputConnection(marchingCubes.getOutputPort())

  // 创建 Actor（vtk 场景中的显示节点），绑定 mapper
  const actor = vtkActor.newInstance()
  actor.setMapper(mapper)
  renderer.addActor(actor)

  // 打印三角面数用于调试
  const polyData = marchingCubes.getOutputData()
  console.log('面数:', polyData.getPolys().getNumberOfCells())

  // 初始化相机并渲染
  renderer.resetCamera()
  renderWindow.render()
})

// 当滑块变化时，更新等值面值并重新渲染
function updateContourValue() {
  if (marchingCubes) {
    marchingCubes.setContourValue(contourValue.value)
    marchingCubes.update()

    // 重新渲染场景
    renderWindow.render()
  }
}
</script>

<style scoped>
.viewer-wrapper {
  display: flex;
  flex-direction: row;
  height: 100vh;
}

.vtk-viewer-container {
  flex: 1;
  background: black;
}

.control-panel {
  width: 250px;
  padding: 1rem;
  background-color: #f4f4f4;
  font-family: sans-serif;
}

.control-panel label {
  display: block;
  margin-bottom: 1rem;
}
</style>
