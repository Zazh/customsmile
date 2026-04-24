from django import forms
from django.urls import reverse
from django.utils.safestring import mark_safe


class ChunkedUploadWidget(forms.Widget):

    def render(self, name, value, attrs=None, renderer=None):
        start_url = reverse("dicom:upload-start")
        # Base URL for chunk/status — JS appends upload_id
        base_url = start_url.replace("start/", "")

        html = f"""
        <div id="chunked-upload-widget">
          <input type="file" id="id_chunked_file" accept=".dcm,.zip" />
          <input type="hidden" name="chunked_upload_id" id="id_chunked_upload_id" />
          <progress id="chunked-progress" value="0" max="100"
                    style="display:none;width:100%;margin-top:8px;height:20px;"></progress>
          <div id="chunked-status"
               style="display:none;margin-top:4px;font-size:12px;color:#666;"></div>
        </div>
        <script>
        document.addEventListener("DOMContentLoaded", function () {{
          var submitBtn = document.querySelector(
            'input[name="_save"], input[name="_continue"], input[name="_addanother"]'
          );
          var csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
          new ChunkedUploader({{
            fileInput: document.getElementById("id_chunked_file"),
            uploadIdInput: document.getElementById("id_chunked_upload_id"),
            progressBar: document.getElementById("chunked-progress"),
            statusText: document.getElementById("chunked-status"),
            submitBtn: submitBtn,
            csrfToken: csrfToken,
            startUrl: "{start_url}",
            chunkUrl: "{base_url}chunk/__upload_id__/",
            statusUrl: "{base_url}status/__upload_id__/",
          }});
        }});
        </script>
        """
        return mark_safe(html)

    def value_from_datadict(self, data, files, name):
        return data.get("chunked_upload_id", "")

    class Media:
        js = ("dicom/chunked_upload.js",)
