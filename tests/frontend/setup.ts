import { config } from '@vue/test-utils'

// These tests exercise setup logic and conditional mounting rather than
// Element Plus internals. Register lightweight global stubs so Vue does not
// emit unresolved-component noise in headless runs.
config.global.stubs = {
  'el-alert': true,
  'el-button': true,
  'el-icon': true,
  'el-input-number': true,
  'el-option': true,
  'el-radio-button': true,
  'el-radio-group': true,
  'el-select': true
}
