(function () {
  "use strict";

  const CHUNK_SIZE = 5 * 1024 * 1024; // 5 MB
  const MAX_RETRIES = 5;
  const RETRY_BASE_MS = 1000;

  function ChunkedUploader(opts) {
    this.fileInput = opts.fileInput;
    this.uploadIdInput = opts.uploadIdInput;
    this.progressBar = opts.progressBar;
    this.statusText = opts.statusText;
    this.submitBtn = opts.submitBtn;
    this.csrfToken = opts.csrfToken;
    this.startUrl = opts.startUrl;
    this.chunkUrl = opts.chunkUrl;
    this.statusUrl = opts.statusUrl;

    this.file = null;
    this.uploadId = null;
    this.offset = 0;
    this.aborted = false;

    this.fileInput.addEventListener("change", this._onFileSelected.bind(this));
  }

  ChunkedUploader.prototype._onFileSelected = function (e) {
    this.file = e.target.files[0];
    if (!this.file) return;

    this.aborted = false;
    this._disableSubmit(true);
    this.statusText.textContent = "Подготовка…";
    this.progressBar.value = 0;
    this.progressBar.max = this.file.size;
    this.progressBar.style.display = "block";
    this.statusText.style.display = "block";

    // Check localStorage for a previous incomplete upload of same file
    var storageKey = "chunked_" + this.file.name + "_" + this.file.size;
    var savedId = localStorage.getItem(storageKey);
    if (savedId) {
      this._resumeExisting(savedId, storageKey);
    } else {
      this._startNew(storageKey);
    }
  };

  ChunkedUploader.prototype._startNew = function (storageKey) {
    var self = this;
    fetch(this.startUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": this.csrfToken,
      },
      body: JSON.stringify({
        filename: this.file.name,
        total_size: this.file.size,
      }),
    })
      .then(function (r) {
        return r.json().then(function (data) {
          return { ok: r.ok, data: data };
        });
      })
      .then(function (res) {
        if (!res.ok) {
          self._setError(res.data.error || "Ошибка создания загрузки");
          return;
        }
        self.uploadId = res.data.upload_id;
        self.offset = 0;
        localStorage.setItem(storageKey, self.uploadId);
        self._sendNextChunk(storageKey);
      })
      .catch(function (err) {
        self._setError("Сеть недоступна: " + err.message);
      });
  };

  ChunkedUploader.prototype._resumeExisting = function (uploadId, storageKey) {
    var self = this;
    var url = this.statusUrl.replace("__upload_id__", uploadId);
    fetch(url, {
      headers: { "X-CSRFToken": this.csrfToken },
    })
      .then(function (r) {
        return r.json().then(function (data) {
          return { ok: r.ok, data: data };
        });
      })
      .then(function (res) {
        if (!res.ok || res.data.status === "failed") {
          localStorage.removeItem(storageKey);
          self._startNew(storageKey);
          return;
        }
        if (res.data.status === "complete") {
          self.uploadId = uploadId;
          self.offset = res.data.total_size;
          self._onComplete(storageKey);
          return;
        }
        self.uploadId = uploadId;
        self.offset = res.data.offset;
        self.progressBar.value = self.offset;
        self.statusText.textContent = "Возобновление с " + self._formatSize(self.offset) + "…";
        self._sendNextChunk(storageKey);
      })
      .catch(function () {
        localStorage.removeItem(storageKey);
        self._startNew(storageKey);
      });
  };

  ChunkedUploader.prototype._sendNextChunk = function (storageKey, retryCount) {
    if (this.aborted) return;
    retryCount = retryCount || 0;

    if (this.offset >= this.file.size) {
      this._onComplete(storageKey);
      return;
    }

    var self = this;
    var end = Math.min(this.offset + CHUNK_SIZE, this.file.size);
    var blob = this.file.slice(this.offset, end);
    var url = this.chunkUrl.replace("__upload_id__", this.uploadId);

    fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/octet-stream",
        "X-CSRFToken": this.csrfToken,
      },
      body: blob,
    })
      .then(function (r) {
        return r.json().then(function (data) {
          return { ok: r.ok, data: data };
        });
      })
      .then(function (res) {
        if (!res.ok) {
          throw new Error(res.data.error || "Chunk upload failed");
        }
        self.offset = res.data.offset;
        self.progressBar.value = self.offset;
        var pct = Math.round((self.offset / self.file.size) * 100);
        self.statusText.textContent =
          self._formatSize(self.offset) + " / " + self._formatSize(self.file.size) + " (" + pct + "%)";
        self._sendNextChunk(storageKey);
      })
      .catch(function (err) {
        if (retryCount < MAX_RETRIES) {
          var delay = RETRY_BASE_MS * Math.pow(2, retryCount);
          self.statusText.textContent =
            "Обрыв связи. Повтор через " + Math.round(delay / 1000) + " сек… (попытка " + (retryCount + 1) + "/" + MAX_RETRIES + ")";
          setTimeout(function () {
            self._sendNextChunk(storageKey, retryCount + 1);
          }, delay);
        } else {
          self._setError("Загрузка не удалась после " + MAX_RETRIES + " попыток: " + err.message);
        }
      });
  };

  ChunkedUploader.prototype._onComplete = function (storageKey) {
    localStorage.removeItem(storageKey);
    this.uploadIdInput.value = this.uploadId;
    this.progressBar.value = this.file.size;
    this.statusText.textContent = "Файл загружен ✓";
    this._disableSubmit(false);
  };

  ChunkedUploader.prototype._setError = function (msg) {
    this.statusText.textContent = "Ошибка: " + msg;
    this.statusText.style.color = "#c00";
    this._disableSubmit(true);
  };

  ChunkedUploader.prototype._disableSubmit = function (disabled) {
    if (this.submitBtn) {
      this.submitBtn.disabled = disabled;
    }
  };

  ChunkedUploader.prototype._formatSize = function (bytes) {
    if (bytes < 1024) return bytes + " Б";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " КБ";
    if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + " МБ";
    return (bytes / (1024 * 1024 * 1024)).toFixed(2) + " ГБ";
  };

  window.ChunkedUploader = ChunkedUploader;
})();
