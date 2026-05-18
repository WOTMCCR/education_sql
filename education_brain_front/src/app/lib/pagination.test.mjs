import test from 'node:test'
import assert from 'node:assert/strict'

import { buildPagination, clampPage } from './pagination.js'

test('buildPagination returns first-page metadata', () => {
  const result = buildPagination(42, 20, 1)

  assert.deepEqual(result, {
    page: 1,
    pageSize: 20,
    totalItems: 42,
    totalPages: 3,
    hasPrevious: false,
    hasNext: true,
    startItem: 1,
    endItem: 20,
  })
})

test('buildPagination clamps pages beyond the end', () => {
  const result = buildPagination(42, 20, 9)

  assert.equal(result.page, 3)
  assert.equal(result.hasPrevious, true)
  assert.equal(result.hasNext, false)
  assert.equal(result.startItem, 41)
  assert.equal(result.endItem, 42)
})

test('buildPagination handles empty results', () => {
  const result = buildPagination(0, 20, 1)

  assert.equal(result.totalPages, 1)
  assert.equal(result.startItem, 0)
  assert.equal(result.endItem, 0)
})

test('clampPage keeps values in range', () => {
  assert.equal(clampPage(-5, 7), 1)
  assert.equal(clampPage(99, 7), 7)
  assert.equal(clampPage(3, 7), 3)
})
