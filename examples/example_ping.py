"""Manual examples. Install the package first (see buildAndReinstall.bat)."""

from rsseismic import RSSeismicApplication

PORT = 60058  # or set RSSEISMIC_SCRIPTING_PORT

app = RSSeismicApplication(port=PORT)
app.ping()
print("RSSeismic scripting server is reachable.")
app.close()
