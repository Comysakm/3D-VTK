<template>
  <!-- <Viewer3D /> -->
  <!-- <IsoSurfaceViewer /> -->
  <!-- <SliceViewer /> -->
    <!-- <ScalarRangeRenderer /> -->
  <!-- <PlyViewer /> -->
    <!-- <ScalarRangePointCloud /> -->
  <!-- <ChoseRangePlyViewer /> -->
   <!-- <DiffCubeViewer /> -->
    <!-- <OctreeViewer/> -->
  <!-- <OctreeByApiViewer/> -->
   <!-- <MultiModelViewer/> -->
    <OctreeBinViewer/>
    <!-- <PointOctreeviewer/> -->
    <!-- <VtpPointViewer/> -->
</template>

<script setup>
import Viewer3D from './components/Viewer3D.vue'
import IsoSurfaceViewer from './components/IsoSurfaceViewer.vue'
import SliceViewer from './components/SliceViewer.vue'
import ScalarRangeRenderer from './components/ScalarRangeRenderer.vue';
import ScalarRangePointCloud from './components/ScalarRange-PointCloud.vue';
import PlyViewer from './components/PlyViewer.vue';
import ChoseRangePlyViewer from './components/ChoseRangePlyViewer.vue';
import ChoseRangeVtpPointViewer from './components/ChoseRangeVtpPointViewer.vue';
import ChoseRangeVtpGlyphViewer from './components/ChoseRangeVtpGlyphViewer.vue';
import ChoseRangeVtiViewer from './components/ChoseRangeVtiViewer.vue';
import ChoseRangeVtpViewer from './components/ChoseRangeVtpViewer.vue';
import DiffCubeViewer from './components/DiffCubeViewer.vue';
import OctreeViewer from './components/OctreeViewer.vue';
// import OctreeByApiViewer from './components/OctreeByApiViewer.vue';
import MultiModelViewer from './components/MultiModelViewer.vue';
import OctreeBinViewer from './components/OctreeBinViewer.vue';
import PointOctreeviewer from './components/PointOctreeviewer.vue';
import VtpPointViewer from './components/VtpPointViewer.vue';
</script>