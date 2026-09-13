with open("docker-compose.yml", "r") as f:
    text = f.read()

target = """  grafana:
    image: grafana/grafana:latest
    volumes:
      - grafana_data:/var/lib/grafana
    environment:"""

replacement = """  grafana:
    image: grafana/grafana:latest
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana/provisioning/datasources:/etc/grafana/provisioning/datasources
      - ./monitoring/grafana/provisioning/dashboards:/etc/grafana/provisioning/dashboards
      - ./monitoring/grafana/dashboards:/var/lib/grafana/dashboards
    environment:"""

text = text.replace(target, replacement)

with open("docker-compose.yml", "w") as f:
    f.write(text)
