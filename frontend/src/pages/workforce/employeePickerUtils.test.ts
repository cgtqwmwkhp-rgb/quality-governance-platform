import { describe, expect, it } from 'vitest'
import {
  ACTIVE_EMPLOYEES_LIST_PARAMS,
  buildEmployeeLabelMap,
  employeePickerOptionLabel,
  employeePrimaryLabel,
  sortEmployeesForPicker,
} from './employeePickerUtils'

describe('employeePickerUtils', () => {
  it('exports active-only list params', () => {
    expect(ACTIVE_EMPLOYEES_LIST_PARAMS).toEqual({
      page: '1',
      page_size: '500',
      is_active: 'true',
    })
  })

  it('builds primary labels with display_name preference', () => {
    expect(
      employeePrimaryLabel({
        id: 1,
        display_name: 'Alex Technician',
        employee_number: 'E-001',
        job_title: 'Tech',
      }),
    ).toBe('Alex Technician')
  })

  it('builds role-aware option labels', () => {
    expect(
      employeePickerOptionLabel({
        id: 2,
        display_name: 'Sam Operator',
        employee_number: 'E-002',
        job_title: 'Plant Operator',
        department: 'Operations',
      }),
    ).toBe('Sam Operator — Plant Operator · Operations')

    expect(
      employeePickerOptionLabel({
        id: 3,
        display_name: null,
        employee_number: 'E-003',
        job_title: 'Joiner',
        department: 'Workshop',
      }),
    ).toBe('E-003 — Joiner · Workshop')
  })

  it('sorts employees by picker label', () => {
    const sorted = sortEmployeesForPicker([
      {
        id: 2,
        external_id: 'x',
        is_active: true,
        employee_number: 'B-002',
      },
      {
        id: 1,
        external_id: 'y',
        is_active: true,
        display_name: 'Alpha',
      },
    ])
    expect(sorted.map((e) => e.id)).toEqual([1, 2])
  })

  it('builds label map for table/filter resolution', () => {
    const map = buildEmployeeLabelMap([
      {
        id: 7,
        external_id: 'z',
        is_active: true,
        employee_number: 'E-007',
        job_title: 'Tech',
      },
    ])
    expect(map[7]).toBe('E-007 — Tech')
  })
})
