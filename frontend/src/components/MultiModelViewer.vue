<template>
  <div class="container">
    <div ref="renderContainer" class="render-window"></div>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from "vue";
import "@kitware/vtk.js/Rendering/Profiles/Geometry";
import vtkFullScreenRenderWindow from "@kitware/vtk.js/Rendering/Misc/FullScreenRenderWindow";
import vtkActor from "@kitware/vtk.js/Rendering/Core/Actor";
import vtkPolyDataMapper from "@kitware/vtk.js/Rendering/Core/Mapper";

import vtkXMLPolyDataReader from "@kitware/vtk.js/IO/XML/XMLPolyDataReader"; // vtp
import vtkPLYReader from "@kitware/vtk.js/IO/Geometry/PLYReader"; // ply
import vtkOBJReader from "@kitware/vtk.js/IO/Misc/OBJReader"; // obj

const renderContainer = ref(null);
let fullScreenRenderer, renderer, renderWindow;

// 获取 polyData 的中心
function getCenter(bounds) {
  const [xmin, xmax, ymin, ymax, zmin, zmax] = bounds;
  return [(xmin + xmax) / 2, (ymin + ymax) / 2, (zmin + zmax) / 2];
}

// 创建 actor
function createActor(data) {
  const mapper = vtkPolyDataMapper.newInstance();
  mapper.setInputData(data);
  const actor = vtkActor.newInstance();
  actor.setMapper(mapper);
  return actor;
}

// 加载模型
async function loadModel(url, type) {
  let reader;
  if (type === "vtp") reader = vtkXMLPolyDataReader.newInstance();
  else if (type === "ply") reader = vtkPLYReader.newInstance();
  else if (type === "obj") reader = vtkOBJReader.newInstance();
  else throw new Error("Unsupported model type: " + type);

  if (type === "obj") {
    const resp = await fetch(url);
    const text = await resp.text();
    reader.parseAsText(text);
  } else {
    const resp = await fetch(url);
    const buffer = await resp.arrayBuffer();
    reader.parseAsArrayBuffer(buffer);
  }

  const data = reader.getOutputData();
  const actor = createActor(data);
  return { actor, data };
}

onMounted(async () => {
  // 初始化渲染器
  fullScreenRenderer = vtkFullScreenRenderWindow.newInstance({
    rootContainer: renderContainer.value,
    background: [0, 0, 0],
  });
  renderer = fullScreenRenderer.getRenderer();
  renderWindow = fullScreenRenderer.getRenderWindow();
  

  // 模型列表
  const models = [
    { url: "/models/cow.vtp", type: "vtp" },
    { url: "/models/horse.ply", type: "ply" },
    { url: "/models/objmodel.obj", type: "obj" },
  ];

  const spacing = 1.5;   // 模型间隔
  const targetSize = 2;   // 统一视觉大小
  let offsetX = 0;
  const allBounds = [];

  for (const m of models) {
    const { actor, data } = await loadModel(m.url, m.type);
    const bounds = data.getBounds();
    const center = getCenter(bounds);

    const width = bounds[1] - bounds[0];
    const height = bounds[3] - bounds[2];
    const depth = bounds[5] - bounds[4];
    const maxSize = Math.max(width, height, depth);

    // 计算缩放比例，使模型最大边长 = targetSize
    const scale = targetSize / maxSize;
    actor.setScale(scale, scale, scale);

    // 居中 + 排列
    actor.setPosition(
      offsetX - center[0] * scale + width * scale / 2,
      -center[1] * scale,
      -center[2] * scale
    );

    offsetX += width * scale + spacing;

    renderer.addActor(actor);
    allBounds.push(bounds);

    console.log(`${m.url} points:`, data.getPoints()?.getNumberOfValues() / 3);
    console.log(`${m.url} bounds:`, bounds);
  }

  // 计算总范围，调整相机保证所有模型可见
  let xmin = Infinity, xmax = -Infinity;
  let ymin = Infinity, ymax = -Infinity;
  let zmin = Infinity, zmax = -Infinity;

  for (let i = 0; i < models.length; i++) {
    const bounds = allBounds[i];
    const scale = targetSize / Math.max(bounds[1]-bounds[0], bounds[3]-bounds[2], bounds[5]-bounds[4]);
    xmin = Math.min(xmin, bounds[0]*scale);
    xmax = Math.max(xmax, (bounds[1]-bounds[0])*scale + xmin);
    ymin = Math.min(ymin, bounds[2]*scale);
    ymax = Math.max(ymax, bounds[3]*scale);
    zmin = Math.min(zmin, bounds[4]*scale);
    zmax = Math.max(zmax, bounds[5]*scale);
  }

  renderer.resetCamera([xmin, xmax, ymin, ymax, zmin, zmax]);
  renderWindow.render();
});

onUnmounted(() => {
  if (fullScreenRenderer) fullScreenRenderer.delete();
});
</script>

<style scoped>
.container {
  display: flex;
  height: 100vh;
}
.render-window {
  flex: 1;
  background: black;
}
</style>
