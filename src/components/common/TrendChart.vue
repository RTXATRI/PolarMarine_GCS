<template>
  <div class="trend" :style="{ height: height + 'px' }">
    <v-chart class="chart" :option="option" autoresize :update-options="{ notMerge: false }" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { use } from 'echarts/core'
import VChart from 'vue-echarts'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent])

interface Props {
  data: number[]
  color?: string
  height?: number
  min?: number
  max?: number
  unit?: string
}
const props = withDefaults(defineProps<Props>(), {
  color: '#3b82f6',
  height: 48,
  min: undefined,
  max: undefined,
  unit: ''
})

const option = computed(() => {
  const data = props.data
  const singlePoint = data.length === 1
  const hasLine = data.length >= 2
  return {
    grid: { top: 4, right: 4, bottom: 4, left: 4 },
    xAxis: { type: 'category', show: false, data: data.map((_, i) => i) },
    yAxis: {
      type: 'value',
      show: false,
      min: props.min,
      max: props.max,
      scale: true
    },
    tooltip: {
      trigger: 'axis',
      formatter: (params: { value: number }[]) => {
        const v = params?.[0]?.value
        return v == null ? '' : `${(+v).toFixed(2)}${props.unit}`
      },
      backgroundColor: 'var(--bg-panel)',
      borderColor: 'var(--border)',
      textStyle: { color: 'var(--text-1)' }
    },
    series: [
      {
        type: 'line',
        smooth: true,
        symbol: singlePoint ? 'circle' : 'none',
        symbolSize: singlePoint ? 4 : 0,
        data,
        lineStyle: { color: props.color, width: hasLine ? 1.5 : 0 },
        areaStyle: hasLine ? {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: props.color + '55' },
              { offset: 1, color: props.color + '00' }
            ]
          }
        } : undefined
      }
    ]
  }
})
</script>

<style scoped>
.trend {
  width: 100%;
}
.chart {
  width: 100%;
  height: 100%;
}
</style>
