from rsseismic import RSSeismicApplication

RSSeismicApplication.startApplication(port=60058)
app = RSSeismicApplication(port=60058)
app.ping()

print("OK")
app.close()
# RSSeismic window stays open; only the Python gRPC client closes