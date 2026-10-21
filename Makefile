IMAGE_TAG ?= latest
ANSIBLE_DIR := ansible
PROM_IMAGE := $(shell sed -nE 's/^prometheus_image:[[:space:]]*"?([^" ]+).*/\1/p' $(ANSIBLE_DIR)/group_vars/all/main.yml)

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

.PHONY: bootstrap deploy update rollback promtool promtool-config gen-dashboards dashboards gen-alerts e2e-logs lint test test-generated smoke

promtool:
	docker run --rm --entrypoint promtool -v "$(CURDIR)/ansible/roles/monitoring/files:/rules:ro" $(PROM_IMAGE) check rules /rules/alerts.yml

gen-dashboards:
	python3 scripts/gen_dashboards.py
	python3 scripts/gen_status_page.py
	python3 scripts/gen_nginx_dashboard.py
	python3 scripts/gen_logs_dashboard.py

dashboards:
	cd $(ANSIBLE_DIR) && ansible-playbook playbook.yml --ask-vault-pass --limit monitoring --tags dashboards

gen-alerts:
	python3 scripts/gen_alerts.py
	python3 scripts/gen_log_alerts.py

promtool-config:
	cd $(ANSIBLE_DIR) && ansible monitoring --ask-vault-pass --become -m command -a "docker exec prometheus promtool check config /etc/prometheus/prometheus.yml"


e2e-logs:
	./scripts/e2e_logs.sh

VAULT_OPT ?= --ask-vault-pass

lint:
	ansible-lint
	python3 -m py_compile scripts/*.py
	bash -n scripts/*.sh

test-generated:
	@before=$$(find ansible/roles/monitoring/files -type f | sort | xargs sha256sum); \
	$(MAKE) -s gen-dashboards gen-alerts > /dev/null; \
	after=$$(find ansible/roles/monitoring/files -type f | sort | xargs sha256sum); \
	if [ "$$before" = "$$after" ]; then echo "OK: сгенерированные файлы актуальны"; else echo "FAIL: сгенерированные файлы были устаревшими, закоммитьте изменения"; exit 1; fi

test: lint test-generated promtool
	cd $(ANSIBLE_DIR) && ansible-playbook playbook.yml $(VAULT_OPT) --syntax-check
	cd $(ANSIBLE_DIR) && ansible all $(VAULT_OPT) -m ping

smoke:
	./scripts/smoke.sh
