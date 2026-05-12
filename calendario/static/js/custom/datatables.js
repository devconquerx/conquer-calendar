'use strict';

var langEs = {
  processing: 'Procesando...',
  lengthMenu: 'Mostrar _MENU_ registros',
  zeroRecords: 'No se encontraron resultados',
  emptyTable: 'Ningún dato disponible en esta tabla',
  info: 'Mostrando registros del _START_ al _END_ de un total de _TOTAL_ registros',
  infoEmpty: 'Mostrando registros del 0 al 0 de un total de 0 registros',
  infoFiltered: '(filtrado de un total de _MAX_ registros)',
  infoPostFix: '',
  search: 'Buscar:',
  url: '',
  infoThousands: ',',
  loadingRecords: 'Cargando...',
  oPaginate: {
    First: 'Primero',
    Last: 'Último',
    Next: 'Siguiente',
    Previous: 'Anterior'
  },
  oAria: {
    SortAscending: ': Activar para ordenar la columna de manera ascendente',
    SortDescending: ': Activar para ordenar la columna de manera descendente'
  }
};

var langEn = {
  emptyTable: 'No data available in table',
  info: 'Showing _START_ to _END_ of _TOTAL_ entries',
  infoEmpty: 'Showing 0 to 0 of 0 entries',
  infoFiltered: '(filtered from _MAX_ total entries)',
  infoPostFix: '',
  infoThousands: ',',
  lengthMenu: 'Show _MENU_ entries',
  loadingRecords: 'Loading...',
  processing: 'Processing...',
  search: 'Search:',
  zeroRecords: 'No matching records found',
  oPaginate: {
    First: 'First',
    Last: 'Last',
    Next: 'Next',
    Previous: 'Previous'
  },
  oAria: {
    SortAscending: ': activate to sort column ascending',
    SortDescending: ': activate to sort column descending'
  }
};

var CustomDatatables = {
  init: function () {
    let table = $('.customDatatable');
    let langSelected = langEs;
    let url = window.location.pathname;
    if (url.indexOf('/en/') != -1) {
      langSelected = langEn;
    }

    // para cada tabla iniciamos el datatable
    $(table).each(function () {
      let pageLength = 20;
      if (this.dataset.pagelength) {
        pageLength = parseInt(this.dataset.pagelength);
      }
      $(this).DataTable({
        responsive: true,
        lengthMenu: [20, 50, 75, 100, 150],
        pageLength: pageLength,
        aaSorting: [],
        order: [],
        language: langSelected,
        "dom":
          "<'row'" +
          "<'col-sm-6 d-flex align-items-center justify-conten-start'l>" +
          "<'col-sm-6 d-flex align-items-center justify-content-end'f>" +
          ">" +
          "<'table-responsive'tr>" +
          "<'row'" +
          "<'col-sm-12 col-md-5 d-flex align-items-center justify-content-center justify-content-md-start'i>" +
          "<'col-sm-12 col-md-7 d-flex align-items-center justify-content-center justify-content-md-end'p>" +
          ">"
      });
    });
  },

  destroy: function () {
    $('.customDatatable').DataTable().destroy();
  },
};


$(document).ready(function () {
  CustomDatatables.init();
  new DataTable('#example', {
    initComplete: function () {
        this.api()
            .columns()
            .every(function () {
                var column = this;
                var columnIndex = column.index();  // Obtiene el índice de la columna

                // Excluir la primera (índice 0) y la última columna
                if (columnIndex === 0) {
                    console.log('entrando');
                } else {
                  var title = $(column.header()).text(); // Obtener el título del encabezado de la columna

                  // Añadir el campo de búsqueda en la segunda fila del thead
                  $('tfoot tr:eq(0) th').eq(columnIndex).html('<input type="text" style="width: 100px" placeholder="' + title + '" />');

                  // Añadir el evento al input de búsqueda
                  $('tfoot tr:eq(0) th input').eq(columnIndex).on('keyup change clear', function () {
                      if (column.search() !== this.value) {
                          column.search(this.value).draw();
                      }
                  });

                }

            });
    },
    layout: {
      top1: {
        searchPanes: {
          viewTotal: true
        }
      }
    }
  });
});
