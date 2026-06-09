import { isValidPhoneNumber } from 'libphonenumber-js'

export function validateBlock(block, value, messages = {}) {
  const req = block.attributes?.required

  if (block.name === 'phone-number') {
    if (!value?.trim()) return false
    try { return isValidPhoneNumber(value) } catch { return false }
  }

  if (block.name === 'long-text') {
    return typeof value === 'string' && value.trim().length >= 1
  }

  if (req && !value?.trim()) return false

  if (block.name === 'email' && value) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)
  }

  return true
}
