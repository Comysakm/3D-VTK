<template>
  <!-- 渲染容器，用于挂载 vtk 的 WebGL 渲染窗口 -->
  <div ref="container" class="vtk-container"></div>
</template>

<script setup>
import { onMounted, ref } from 'vue'

import '@kitware/vtk.js/Rendering/Profiles/Volume'
import vtkFullScreenRenderWindow from '@kitware/vtk.js/Rendering/Misc/FullScreenRenderWindow'
import vtkXMLImageDataReader from '@kitware/vtk.js/IO/XML/XMLImageDataReader'
import vtkVolume from '@kitware/vtk.js/Rendering/Core/Volume'
import vtkVolumeMapper from '@kitware/vtk.js/Rendering/Core/VolumeMapper'
import vtkColorTransferFunction from '@kitware/vtk.js/Rendering/Core/ColorTransferFunction'
import vtkPiecewiseFunction from '@kitware/vtk.js/Common/DataModel/PiecewiseFunction'

// Vue ref：绑定 HTML 渲染容器
const container = ref(null)

onMounted(() => {
  // 创建全屏渲染窗口，并开启离屏缓冲以优化性能
  const fullScreenRenderer = vtkFullScreenRenderWindow.newInstance({
    rootContainer: container.value,
    background: [0, 0, 0],           
    useOffscreenBuffers: true,       // 启用离屏渲染以提高体绘制性能
  })

  const renderer = fullScreenRenderer.getRenderer()
  const renderWindow = fullScreenRenderer.getRenderWindow()

  // 打印浏览器是否支持 WebGL 2.0（性能更好）
  const isWebGL2 = !!window.WebGL2RenderingContext
  console.log('WebGL 2.0 supported:', isWebGL2)

  // 加载 .vti
  fetch('/SaltfFF.vti') 
    .then(response => response.arrayBuffer())
    .then(arrayBuffer => {
      // 创建 VTK 读取器并解析数据
      const reader = vtkXMLImageDataReader.newInstance()
      reader.parseAsArrayBuffer(arrayBuffer)
      const imageData = reader.getOutputData(0)

      // 创建体绘制 Mapper，连接数据源
      const mapper = vtkVolumeMapper.newInstance()
      mapper.setSampleDistance(2.0) // 设置采样距离（数值越小质量越高，越大性能越好）
      mapper.setInputData(imageData)

      // 创建体对象并绑定 mapper
      const volume = vtkVolume.newInstance()
      volume.setMapper(mapper)

      // 颜色映射函数（决定体素值对应的颜色）
      const ctfun = vtkColorTransferFunction.newInstance()
      ctfun.addRGBPoint(1500, 0, 0.3, 0.3)     // 黑暗红色区域：低值
      ctfun.addRGBPoint(2477.0, 0.0, 0.8, 0.8) // 青色区域：中间值
      ctfun.addRGBPoint(4482.0, 1.0, 1.0, 1.0) // 白色区域：高值

      // 不透明度映射函数（决定体素值是否可见）
      const ofun = vtkPiecewiseFunction.newInstance()
      ofun.addPoint(1500, 0.0)      // 完全透明
      ofun.addPoint(2477.0, 0.3)    // 中间值逐渐显现
      ofun.addPoint(4482.0, 0.6)    // 接近最大值时较不透明

      // 绑定传输函数到体属性
      volume.getProperty().setRGBTransferFunction(0, ctfun)
      volume.getProperty().setScalarOpacity(0, ofun)
      volume.getProperty().setInterpolationTypeToLinear() // 设置线性插值

      // 将体对象添加到渲染器中
      renderer.addVolume(volume)

      // 重设相机视角并渲染
      renderer.resetCamera()
      renderWindow.render()
    })
})
</script>

<style scoped>
/* 保证 vtk 渲染区域铺满整个屏幕 */
.vtk-container {
  width: 100%;
  height: 100vh;
  overflow: hidden;
}
</style>
