<template>
  <div class="trend-chart" :style="{ height: `${height}px` }">
    <VChart class="chart" :option="option" autoresize :update-options="{ notMerge: false }" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent])

const props = withDefaults(
  defineProps<{
    data: number[]
    color?: string
    height?: number
    min?: number
    max?: number
    unit?: string
  }>(),
  { color: '#3b82f6', height: 48, min: undefined, max: undefined, unit: '' }
)

const option = computed(() => {
  const hasLine = props.data.length >= 2
  return {
    animation: false,
    grid: { top: 4, right: 4, bottom: 4, left: 4 },
    xAxis: {
      type: 'category',
      show: false,
      data: props.data.map((_, index) => index)
    },
    yAxis: {
      type: 'value',
      show: false,
      min: props.min,
      max: props.max,
      scale: true
    },
    tooltip: {
      trigger: 'axis',
      formatter: (params: Array<{ value: number }>) => {
        const value = params[0]?.value
        return value == null ? '' : `${Number(value).toFixed(2)}${props.unit}`
      },
      backgroundColor: 'var(--bg-panel)',
      borderColor: 'var(--border)',
      textStyle: { color: 'var(--text-1)' }
    },
    series: [
      {
        type: 'line',
        smooth: true,
        symbol: props.data.length === 1 ? 'circle' : 'none',
        symbolSize: 4,
        data: props.data,
        lineStyle: { color: props.color, width: hasLine ? 1.5 : 0 },
        areaStyle: hasLine
          ? {
              color: {
                type: 'linear',
                x: 0,
                y: 0,
                x2: 0,
                y2: 1,
                colorStops: [
                  { offset: 0, color: `${props.color}55` },
                  { offset: 1, color: `${props.color}00` }
                ]
              }
            }
          : undefined
      }
    ]
  }
})
</script>

<style scoped>
.trend-chart,
.chart {
  width: 100%;
}

.chart {
  height: 100%;
}
</style>
