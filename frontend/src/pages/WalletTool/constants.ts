/** Reserved user spend row; matches backend `ALL_OTHER_SPEND_NAME`. */
export const LOCKED_USER_SPEND_CATEGORY_NAME = 'All Other'

export function isLockedUserSpendCategoryName(name: string): boolean {
  return name === LOCKED_USER_SPEND_CATEGORY_NAME
}
