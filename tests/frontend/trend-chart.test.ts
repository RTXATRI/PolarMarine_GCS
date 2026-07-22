import { describe, expect, it } from 'vitest'
import { shallowMount } from '@vue/test-utils'
import TrendChart from '../../src/components/common/TrendChart.vue'

interface TrendSeries {
  symbol: string
  symbolSize: number
  lineStyle: { width: number }
  areaStyle?: object
}

function seriesOf(wrapper: ReturnType<typeof shallowMount>): TrendSeries {
  const vm = wrapper.vm as unknown as {
    option: { series: TrendSeries[] }
  }
  return vm.option.series[0]
}

describe('TrendChart', () => {
  it('shows a point without a line or area for the first sample', () => {
    const wrapper = shallowMount(TrendChart, { props: { data: [42] } })
    const series = seriesOf(wrapper)

    expect(series.symbol).toBe('circle')
    expect(series.symbolSize).toBeGreaterThan(0)
    expect(series.lineStyle.width).toBe(0)
    expect(series.areaStyle).toBeUndefined()
  })

  it('draws a line and area once there are at least two samples', () => {
    const wrapper = shallowMount(TrendChart, { props: { data: [42, 43] } })
    const series = seriesOf(wrapper)

    expect(series.symbol).toBe('none')
    expect(series.lineStyle.width).toBeGreaterThan(0)
    expect(series.areaStyle).toBeDefined()
  })
})
