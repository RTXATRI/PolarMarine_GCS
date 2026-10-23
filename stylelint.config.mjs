export default {
  extends: ['stylelint-config-standard-scss', 'stylelint-config-recommended-vue/scss'],
  rules: {
    'selector-class-pattern': null,
    'no-descending-specificity': null,
    'custom-property-pattern': null,
    'scss/at-rule-no-unknown': true
  }
}
