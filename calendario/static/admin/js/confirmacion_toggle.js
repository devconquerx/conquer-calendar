(function () {
  'use strict'
  function toggle() {
    var tipo = document.getElementById('id_confirmacion_tipo')
    var urlRow = document.querySelector('.field-confirmacion_url')
    if (!tipo || !urlRow) return
    var input = urlRow.querySelector('input')
    if (tipo.value === 'url') {
      urlRow.style.opacity = ''
      if (input) input.readOnly = false
    } else {
      urlRow.style.opacity = '0.4'
      if (input) input.readOnly = true
    }
  }
  document.addEventListener('DOMContentLoaded', function () {
    toggle()
    var tipo = document.getElementById('id_confirmacion_tipo')
    if (tipo) tipo.addEventListener('change', toggle)
  })
})()
