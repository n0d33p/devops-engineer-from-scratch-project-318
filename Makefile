IMAGE_TAG ?= latest
ANSIBLE_DIR := ansible

bootstrap:
	cd $(ANSIBLE_DIR) && ansible-galaxy role install -r requirements.yml
	cd $(ANSIBLE_DIR) && ansible-galaxy collection install -r requirements.yml

deploy:
	cd $(ANSIBLE_DIR) && ansible-playbook playbook.yml --ask-vault-pass -e image_tag=$(IMAGE_TAG)

update:
	cd $(ANSIBLE_DIR) && ansible-playbook update.yml --ask-vault-pass -e image_tag=$(IMAGE_TAG)

rollback:
	@test "$(IMAGE_TAG)" != "latest" || (echo "Usage: make rollback IMAGE_TAG=<previous-stable-tag>"; exit 1)
	cd $(ANSIBLE_DIR) && ansible-playbook update.yml --ask-vault-pass -e image_tag=$(IMAGE_TAG)

.PHONY: bootstrap deploy update rollback promtool promtool-config gen-dashboards dashboards gen-alerts

promtool:
	docker run --rm --entrypoint promtool -v "$(CURDIR)/ansible/roles/monitoring/files:/rules:ro" prom/prometheus:v3.13.2 check rules /rules/alerts.yml

gen-dashboards:
	python3 scripts/gen_dashboards.py
	python3 scripts/gen_status_page.py
	python3 scripts/gen_nginx_dashboard.py

dashboards:
	cd $(ANSIBLE_DIR) && ansible-playbook playbook.yml --ask-vault-pass --limit monitoring --tags dashboards

gen-alerts:
	python3 scripts/gen_alerts.py

promtool-config:
	cd $(ANSIBLE_DIR) && ansible monitoring --ask-vault-pass --become -m command -a "docker exec prometheus promtool check config /etc/prometheus/prometheus.yml"

