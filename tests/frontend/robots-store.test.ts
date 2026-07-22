import { beforeEach, describe, expect, it } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useRobotsStore } from '../../src/stores/robots'
import { makeRobot } from './fixtures'

describe('robots store connection ordering', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('sorts connected first and connecting second without changing registry order', () => {
    const store = useRobotsStore()
    const original = [
      makeRobot('saved-a'),
      makeRobot('saved-b', { state: 'connected', activeMethod: 'network', dataMode: 'virtual' }),
      makeRobot('saved-c', { state: 'connecting', activeMethod: 'serial', endpoint: 'COM3' }),
      makeRobot('saved-d', { state: 'error', error: { code: 'OPEN_FAILED', message: 'failed' } })
    ]

    store.replaceAll(original)

    expect(store.sortedRobots.map(robot => robot.id)).toEqual(['saved-b', 'saved-c', 'saved-a', 'saved-d'])
    expect(store.robots.map(robot => robot.id)).toEqual(['saved-a', 'saved-b', 'saved-c', 'saved-d'])
  })

  it('preserves the selected device when a connection update changes ordering', () => {
    const store = useRobotsStore()
    store.replaceAll([makeRobot('a'), makeRobot('b'), makeRobot('c')])
    store.select('c')

    store.replaceAll([
      makeRobot('a'),
      makeRobot('b', { state: 'connected', activeMethod: 'network', dataMode: 'virtual' }),
      makeRobot('c')
    ])

    expect(store.selectedId).toBe('c')
    expect(store.selected?.id).toBe('c')
    expect(store.sortedRobots[0].id).toBe('b')
  })

  it('derives the compatibility online flag from connection state', () => {
    const store = useRobotsStore()
    const inconsistent = makeRobot('robot')
    inconsistent.online = true

    store.replaceAll([inconsistent])

    expect(store.robots[0].online).toBe(false)
  })
})
