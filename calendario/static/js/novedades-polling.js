(function() {
  'use strict';

  var bellBtn = document.getElementById('novedades-bell-btn');
  if (!bellBtn) return;

  var badge = document.getElementById('novedades-badge');
  var dropdownList = document.getElementById('novedades-dropdown-list');
  var countUrl = bellBtn.dataset.countUrl;
  var recentUrl = bellBtn.dataset.recentUrl;

  // Polling cada 60 segundos
  function pollCount() {
    fetch(countUrl, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function(resp) { return resp.json(); })
      .then(function(data) {
        updateBadge(data.count);
      })
      .catch(function() {});
  }

  function updateBadge(count) {
    if (!badge) return;
    badge.textContent = count;
    badge.style.display = count > 0 ? '' : 'none';
    if (count > 0) {
      badge.classList.add('has-novedades');
      bellBtn.classList.add('has-novedades');
      // Re-trigger animation
      badge.style.animation = 'none';
      bellBtn.querySelector('.bi-bell').style.animation = 'none';
      void badge.offsetWidth; // force reflow
      badge.style.animation = '';
      bellBtn.querySelector('.bi-bell').style.animation = '';
    } else {
      badge.classList.remove('has-novedades');
      bellBtn.classList.remove('has-novedades');
    }
  }

  setInterval(pollCount, 60000);

  // Cargar recientes al abrir dropdown
  var dropdownLoaded = false;
  bellBtn.addEventListener('click', function() {
    dropdownLoaded = false;
    loadRecent();
  });

  function loadRecent() {
    if (!dropdownList || !recentUrl) return;
    dropdownList.innerHTML = '<div class="text-center py-4"><span class="spinner-border spinner-border-sm"></span></div>';

    fetch(recentUrl, { headers: { 'X-Requested-With': 'XMLHttpRequest' } })
      .then(function(resp) { return resp.json(); })
      .then(function(data) {
        if (!data.novedades || data.novedades.length === 0) {
          dropdownList.innerHTML = '<div class="text-center py-5 text-gray-500">Sin novedades pendientes</div>';
          return;
        }
        var html = '';
        data.novedades.forEach(function(n) {
          var icons = {
            'new_ticket': '<i class="bi bi-ticket-perforated text-warning fs-4"></i>',
            'ticket_reply': '<i class="bi bi-chat-dots text-info fs-4"></i>',
            'transfer_payment': '<i class="bi bi-bank text-primary fs-4"></i>',
          };
          var icon = icons[n.type] || '<i class="bi bi-bell text-secondary fs-4"></i>';
          var link = n.source_url
            ? '<a href="' + n.source_url + '" class="text-gray-900 fw-semibold text-hover-primary">' + escapeHtml(n.title) + '</a>'
            : '<span class="text-gray-900 fw-semibold">' + escapeHtml(n.title) + '</span>';

          html += '<div class="d-flex align-items-start py-3 px-4 border-bottom border-gray-200" id="novedad-dropdown-' + n.id + '">'
            + '<div class="symbol symbol-35px me-3 mt-1"><span class="symbol-label bg-light">' + icon + '</span></div>'
            + '<div class="flex-grow-1">'
            + '<div class="fs-7">' + link + '</div>'
            + '<div class="fs-8 text-gray-500 mt-1">' + escapeHtml(n.type_display) + ' &middot; ' + escapeHtml(n.created) + '</div>'
            + '</div>'
            + '<button type="button" class="btn btn-sm btn-icon btn-light-success ms-2 mt-1 btn-resolve-dropdown" '
            + 'data-resolve-url="' + n.resolve_url + '" data-novedad-id="' + n.id + '" title="Resolver">'
            + '<i class="bi bi-check-lg"></i></button>'
            + '</div>';
        });
        dropdownList.innerHTML = html;
        bindResolveButtons();
        dropdownLoaded = true;
      })
      .catch(function() {
        dropdownList.innerHTML = '<div class="text-center py-4 text-danger">Error al cargar</div>';
      });
  }

  function bindResolveButtons() {
    dropdownList.querySelectorAll('.btn-resolve-dropdown').forEach(function(btn) {
      btn.addEventListener('click', function(e) {
        e.stopPropagation();
        var resolveUrl = this.dataset.resolveUrl;
        var novedadId = this.dataset.novedadId;
        var row = document.getElementById('novedad-dropdown-' + novedadId);
        var csrfToken = getCsrfToken();

        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';

        fetch(resolveUrl, {
          method: 'POST',
          headers: {
            'X-CSRFToken': csrfToken,
            'X-Requested-With': 'XMLHttpRequest',
          },
        })
        .then(function(resp) { return resp.json(); })
        .then(function(data) {
          if (data.ok) {
            row.style.transition = 'opacity 0.3s';
            row.style.opacity = '0';
            setTimeout(function() {
              row.remove();
              // Si no quedan items, mostrar mensaje vacio
              if (!dropdownList.querySelector('.d-flex')) {
                dropdownList.innerHTML = '<div class="text-center py-5 text-gray-500">Sin novedades pendientes</div>';
              }
            }, 300);
            // Actualizar badge
            updateBadge(data.count);
            // Tambien actualizar en la lista completa si existe
            var listRow = document.getElementById('novedad-row-' + novedadId);
            if (listRow) listRow.remove();
          }
        })
        .catch(function() {
          btn.disabled = false;
          btn.innerHTML = '<i class="bi bi-check-lg"></i>';
        });
      });
    });
  }

  function getCsrfToken() {
    var cookie = document.cookie.match(/csrftoken=([^;]+)/);
    return cookie ? cookie[1] : '';
  }

  function escapeHtml(str) {
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(str));
    return div.innerHTML;
  }
})();
