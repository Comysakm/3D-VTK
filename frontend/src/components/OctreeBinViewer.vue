<!--
  代码功能说明：
  这是一个基于 Vue 3 和 VTK.js 的八叉树体渲染组件，用于加载自定义二进制八叉树文件并进行高效体渲染。
  组件通过解析八叉树结构重建体数据，应用颜色映射和不透明度映射进行可视化，支持交互式体素渲染。

  基本流程：
  1. 初始化 VTK.js 渲染管线，创建全屏渲染窗口并启用离屏缓冲以优化性能。
  2. 加载八叉树二进制文件，解析头部信息和递归节点结构。
  3. 重建体数据为 ImageData 格式，保持原始体素分辨率和标量值。
  4. 配置体渲染管线，包括采样距离、颜色映射和不透明度映射。
  5. 添加交互控件，调整相机视角并触发渲染更新。

  颜色映射修改位置：
  第 85-91 行 - ctfun.addRGBPoint() 调用，定义标量值到 RGB 颜色的映射。
  第 94-98 行 - ofun.addPoint() 调用，定义标量值到不透明度的映射。
  建议修改策略：
  - 低值区域（0-25%）：深蓝色到浅蓝色，透明度 0-0.1
  - 中值区域（25%-75%）：绿色到黄色，不透明度 0.2-0.5  
  - 高值区域（75%-100%）：橙色到红色，不透明度 0.6-0.8
-->

<template>
  <!-- 渲染容器，绑定 VTK.js WebGL 上下文 -->
  <div ref="container" class="octree-render-container">
    <!-- 加载状态指示器 -->
    <div v-if="loading" class="loading-overlay">
      <div class="loading-spinner"></div>
      <p>正在解析八叉树数据...</p>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref, onUnmounted } from 'vue';
import '@kitware/vtk.js/Rendering/Profiles/Volume'; // 加载体渲染模块
import vtkFullScreenRenderWindow from '@kitware/vtk.js/Rendering/Misc/FullScreenRenderWindow'; // 全屏渲染窗口
import vtkVolume from '@kitware/vtk.js/Rendering/Core/Volume'; // 体渲染对象
import vtkVolumeMapper from '@kitware/vtk.js/Rendering/Core/VolumeMapper'; // 体数据映射器
import vtkColorTransferFunction from '@kitware/vtk.js/Rendering/Core/ColorTransferFunction'; // 颜色传输函数
import vtkPiecewiseFunction from '@kitware/vtk.js/Common/DataModel/PiecewiseFunction'; // 分段函数（不透明度）
import vtkImageData from '@kitware/vtk.js/Common/DataModel/ImageData'; // 体数据结构
import vtkDataArray from '@kitware/vtk.js/Common/Core/DataArray'; // 数据数组
import vtkBoundingBox from '@kitware/vtk.js/Common/DataModel/BoundingBox'; // 边界框工具

// 响应式状态变量
const container = ref(null); // 渲染容器引用
const loading = ref(true); // 数据加载状态
let fullScreenRenderer = null; // 渲染窗口实例
let renderWindow = null; // 渲染窗口对象

// 八叉树文件解析函数
const parseOctreeFile = async (filePath) => {
  try {
    // 异步加载八叉树文件
    const response = await fetch(filePath);
    const arrayBuffer = await response.arrayBuffer();
    const view = new DataView(arrayBuffer);
    
    // 解析文件头部：读取维度信息 (little-endian uint32)
    let pos = 0;
    const nx = view.getUint32(pos, true); pos += 4; // X 维度
    const ny = view.getUint32(pos, true); pos += 4; // Y 维度
    const nz = view.getUint32(pos, true); pos += 4; // Z 维度
    
    console.log(`八叉树维度：${nx} × ${ny} × ${nz}`);
    
    // 创建体素数据数组
    const totalVoxels = nx * ny * nz;
    const data = new Float32Array(totalVoxels);
    
    // 递归解析八叉树节点
    const parseNode = (minX, minY, minZ, sizeX, sizeY, sizeZ) => {
      // 读取节点类型标识 (1 字节)
      const nodeType = view.getUint8(pos); 
      pos++;
      
      if (nodeType === 0) {
        // 叶子节点：读取标量值 (little-endian float32)
        const value = view.getFloat32(pos, true);
        pos += 4;
        
        // 填充该子空间的所有体素
        for (let z = 0; z < sizeZ; z++) {
          for (let y = 0; y < sizeY; y++) {
            for (let x = 0; x < sizeX; x++) {
              const globalX = minX + x;
              const globalY = minY + y;
              const globalZ = minZ + z;
              
              // 计算全局体素索引 (Z-major 顺序)
              const index = globalZ * (ny * nx) + globalY * nx + globalX;
              data[index] = value;
            }
          }
        }
      } else {
        // 内部节点：递归处理 8 个子节点
        const halfX = Math.floor((sizeX + 1) / 2);
        const halfY = Math.floor((sizeY + 1) / 2);
        const halfZ = Math.floor((sizeZ + 1) / 2);
        
        // 定义 8 个子节点的尺寸和位置
        const childConfigs = [
          { x: minX, y: minY, z: minZ, sx: halfX, sy: halfY, sz: halfZ },
          { x: minX, y: minY, z: minZ + halfZ, sx: halfX, sy: halfY, sz: sizeZ - halfZ },
          { x: minX, y: minY + halfY, z: minZ, sx: halfX, sy: sizeY - halfY, sz: halfZ },
          { x: minX, y: minY + halfY, z: minZ + halfZ, sx: halfX, sy: sizeY - halfY, sz: sizeZ - halfZ },
          { x: minX + halfX, y: minY, z: minZ, sx: sizeX - halfX, sy: halfY, sz: halfZ },
          { x: minX + halfX, y: minY, z: minZ + halfZ, sx: sizeX - halfX, sy: halfY, sz: sizeZ - halfZ },
          { x: minX + halfX, y: minY + halfY, z: minZ, sx: sizeX - halfX, sy: sizeY - halfY, sz: halfZ },
          { x: minX + halfX, y: minY + halfY, z: minZ + halfZ, sx: sizeX - halfX, sy: sizeY - halfY, sz: sizeZ - halfZ }
        ];
        
        // 递归解析每个子节点
        childConfigs.forEach(config => {
          parseNode(config.x, config.y, config.z, config.sx, config.sy, config.sz);
        });
      }
    };
    
    // 从根节点开始解析整个八叉树
    parseNode(0, 0, 0, nx, ny, nz);
    
    // 验证解析完成
    if (pos !== arrayBuffer.byteLength) {
      console.warn(`八叉树解析可能不完整：期望 ${arrayBuffer.byteLength} 字节，实际 ${pos} 字节`);
    }
    
    return { nx, ny, nz, data };
  } catch (error) {
    console.error('八叉树文件解析失败：', error);
    throw error;
  }
};

// 组件挂载时的初始化逻辑
onMounted(async () => {
  try {
    // 创建全屏渲染窗口，配置性能优化参数
    fullScreenRenderer = vtkFullScreenRenderWindow.newInstance({
      rootContainer: container.value,
      background: [0.1, 0.1, 0.15], // 深灰色背景，减少视觉干扰
      useOffscreenBuffers: true, // 启用离屏缓冲提高体渲染性能
    });
    
    // 获取核心渲染组件
    const renderer = fullScreenRenderer.getRenderer();
    renderWindow = fullScreenRenderer.getRenderWindow();
    
    // 检测 WebGL 2.0 支持状态
    const gl = renderWindow.getWebGLRenderingContext();
    const webglVersion = gl ? (gl instanceof WebGL2RenderingContext ? 2 : 1) : 0;
    console.log(`WebGL 版本：${webglVersion}`);
    
    // 解析八叉树文件并构建体数据
    const { nx, ny, nz, data } = await parseOctreeFile('./octree.bin');
    
    // 创建 VTK ImageData 结构
    const imageData = vtkImageData.newInstance();
    imageData.setDimensions(nx, ny, nz); // 设置体素分辨率
    imageData.setOrigin(0, 0, 0); // 数据原点
    imageData.setSpacing(20, 20, 20); // 体素间距（来自原始文件格式）
    
    // 创建标量数据数组并绑定到 ImageData
    const scalars = vtkDataArray.newInstance({
      name: 'OctreeScalars', // 数据数组名称
      values: data, // 解析后的标量值
      numberOfComponents: 1, // 单通道标量数据
    });
    imageData.getPointData().setScalars(scalars);
    
    // 获取数据范围用于映射函数配置
    const dataRange = scalars.getRange();
    console.log(`标量值范围：[${dataRange[0].toFixed(2)}, ${dataRange[1].toFixed(2)}]`);
    
    // 配置体渲染映射器
    const mapper = vtkVolumeMapper.newInstance();
    // 自适应采样距离：基于体素间距的 70%（平衡质量和性能）
    const spacingSum = imageData.getSpacing().reduce((a, b) => a + b, 0);
    const sampleDistance = 0.7 * Math.sqrt(spacingSum * spacingSum / 3);
    mapper.setSampleDistance(sampleDistance);
    mapper.setInputData(imageData);
    
    // 创建体渲染对象
    const volume = vtkVolume.newInstance();
    volume.setMapper(mapper);
    
    // ===== 颜色映射配置（修改此区域以调整可视化效果） =====
    // 配置 RGB 颜色传输函数：标量值 → 颜色
    const ctfun = vtkColorTransferFunction.newInstance();
    // 低值区域：深蓝色到浅蓝色（冷色调）
    ctfun.addRGBPoint(dataRange[0], 0.0, 0.2, 0.8); // 最小值 - 深蓝
    ctfun.addRGBPoint(dataRange[0] + 0.25 * (dataRange[1] - dataRange[0]), 0.0, 0.6, 1.0); // 25% - 亮蓝
    
    // 中值区域：绿色到黄色（暖色过渡）
    ctfun.addRGBPoint(dataRange[0] + 0.5 * (dataRange[1] - dataRange[0]), 0.6, 1.0, 0.2); // 50% - 亮绿
    ctfun.addRGBPoint(dataRange[0] + 0.75 * (dataRange[1] - dataRange[0]), 1.0, 1.0, 0.0); // 75% - 亮黄
    
    // 高值区域：橙色到红色（高亮显示）
    ctfun.addRGBPoint(dataRange[1], 1.0, 0.3, 0.0); // 最大值 - 鲜红
    
    // 配置不透明度传输函数：标量值 → 透明度
    const ofun = vtkPiecewiseFunction.newInstance();
    // 低值区域：高透明（几乎不可见）
    ofun.addPoint(dataRange[0], 0.0); // 最小值 - 完全透明
    ofun.addPoint(dataRange[0] + 0.25 * (dataRange[1] - dataRange[0]), 0.1); // 25% - 微透明
    
    // 中值区域：中等不透明度
    ofun.addPoint(dataRange[0] + 0.5 * (dataRange[1] - dataRange[0]), 0.4); // 50% - 半透明
    ofun.addPoint(dataRange[0] + 0.75 * (dataRange[1] - dataRange[0]), 0.6); // 75% - 较不透明
    
    // 高值区域：低透明（清晰可见）
    ofun.addPoint(dataRange[1], 0.8); // 最大值 - 高度不透明
    // ===== 颜色映射配置结束 =====
    
    // 配置体渲染属性
    const property = volume.getProperty();
    property.setRGBTransferFunction(0, ctfun); // 绑定颜色映射
    property.setScalarOpacity(0, ofun); // 绑定不透明度映射
    
    // 渲染质量配置
    property.setInterpolationTypeToLinear(); // 线性插值平滑过渡
    property.setUseGradientOpacity(0, true); // 启用梯度不透明度增强边缘
    // 梯度不透明度阈值：基于数据范围的 5%
    const gradientRange = (dataRange[1] - dataRange[0]) * 0.05;
    property.setGradientOpacityMinimumValue(0, 0);
    property.setGradientOpacityMaximumValue(0, gradientRange);
    
    // 光照和材质配置
    property.setShade(true); // 启用阴影效果
    property.setAmbient(0.15); // 环境光强度
    property.setDiffuse(0.75); // 漫反射强度
    property.setSpecular(0.25); // 镜面反射强度
    property.setSpecularPower(16.0); // 镜面高光锐度
    
    // 标量不透明度单位距离：基于体数据的几何特性
    const bounds = imageData.getBounds();
    const diagonalLength = vtkBoundingBox.getDiagonalLength(bounds);
    const maxDimension = Math.max(...imageData.getDimensions());
    property.setScalarOpacityUnitDistance(0, diagonalLength / maxDimension);
    
    // 将体对象添加到渲染场景
    renderer.addVolume(volume);
    
    // 配置相机：自适应体数据边界
    renderer.resetCamera();
    renderer.resetCameraClippingRange(); // 重置裁剪范围
    
    // 触发首次渲染
    renderWindow.render();
    
    // 更新加载状态
    loading.value = false;
    
    console.log('八叉树体渲染初始化完成');
    
  } catch (error) {
    console.error('渲染初始化失败：', error);
    loading.value = false;
  }
});

// 组件卸载时的清理逻辑
onUnmounted(() => {
  if (fullScreenRenderer) {
    fullScreenRenderer.delete();
    fullScreenRenderer = null;
    renderWindow = null;
  }
});
</script>

<style scoped>
/* 渲染容器样式配置 */
.octree-render-container {
  width: 100%;
  height: 100vh;
  position: relative;
  overflow: hidden;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
}

/* 加载覆盖层样式 */
.loading-overlay {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.8);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  color: #ffffff;
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
}

.loading-spinner {
  width: 50px;
  height: 50px;
  border: 4px solid rgba(255, 255, 255, 0.3);
  border-top: 4px solid #4facfe;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 20px;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.loading-overlay p {
  font-size: 16px;
  margin: 0;
  text-shadow: 0 2px 4px rgba(0, 0, 0, 0.5);
}
</style>