import { describe, expect, it } from 'vitest'
import {
  QUESTION_TYPE_MENU_MAX_PX,
  QUESTION_TYPES,
  computeQuestionTypeMenuPlacement,
} from '../QuestionEditor'

describe('computeQuestionTypeMenuPlacement', () => {
  it('clamps list height to available space below the trigger', () => {
    const trigger = {
      top: 500,
      bottom: 540,
      left: 40,
      right: 200,
      width: 160,
      height: 40,
      x: 40,
      y: 500,
      toJSON() {
        return {}
      },
    } as DOMRect
    const { listMaxHeight, menuStyle } = computeQuestionTypeMenuPlacement(trigger, {
      width: 1280,
      height: 700,
    })
    // 700 - 540 - 4 = 156px available below
    expect(listMaxHeight).toBe(156)
    expect(listMaxHeight).toBeLessThan(QUESTION_TYPE_MENU_MAX_PX)
    expect(menuStyle.top).toBe(544)
    expect(menuStyle.maxHeight).toBe(156)
  })

  it('opens upward when there is more room above than below', () => {
    const trigger = {
      top: 620,
      bottom: 660,
      left: 40,
      right: 200,
      width: 160,
      height: 40,
      x: 40,
      y: 620,
      toJSON() {
        return {}
      },
    } as DOMRect
    const { listMaxHeight, menuStyle } = computeQuestionTypeMenuPlacement(trigger, {
      width: 1280,
      height: 700,
    })
    expect(menuStyle.bottom).toBeDefined()
    expect(menuStyle.top).toBeUndefined()
    expect(listMaxHeight).toBeGreaterThan(120)
  })

  it('exposes more question types than fit in a short viewport (scroll required)', () => {
    expect(QUESTION_TYPES.length).toBeGreaterThan(6)
  })
})
