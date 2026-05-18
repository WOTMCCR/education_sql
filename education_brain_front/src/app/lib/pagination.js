export function buildPagination(totalItems, pageSize, currentPage) {
  const safeTotalItems = Number.isFinite(totalItems) ? Math.max(0, Math.trunc(totalItems)) : 0
  const safePageSize = Number.isFinite(pageSize) ? Math.max(1, Math.trunc(pageSize)) : 1
  const totalPages = Math.max(1, Math.ceil(safeTotalItems / safePageSize))
  const page = clampPage(currentPage, totalPages)

  return {
    page,
    pageSize: safePageSize,
    totalItems: safeTotalItems,
    totalPages,
    hasPrevious: page > 1,
    hasNext: page < totalPages,
    startItem: safeTotalItems === 0 ? 0 : (page - 1) * safePageSize + 1,
    endItem: safeTotalItems === 0 ? 0 : Math.min(page * safePageSize, safeTotalItems),
  }
}

export function clampPage(page, totalPages) {
  const safeTotalPages = Number.isFinite(totalPages) ? Math.max(1, Math.trunc(totalPages)) : 1
  const safePage = Number.isFinite(page) ? Math.trunc(page) : 1

  if (safePage < 1) return 1
  if (safePage > safeTotalPages) return safeTotalPages
  return safePage
}
