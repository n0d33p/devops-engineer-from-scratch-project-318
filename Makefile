ANSIBLE_DIR := ansible
PROM_IMAGE := $(shell sed -nE 's/^prometheus_image:[[:space:]]*"?([^" ]+).*/\1/p' $(ANSIBLE_DIR)/group_vars/all/main.yml)
IMAGE_TAG ?= latest
VAULT_OPT ?= --ask-vault-pass
ANSIBLE_PLAYBOOK = cd $(ANSIBLE_DIR) && ansible-playbook

bootstrap:
	ansible-galaxy role install -r requirements.yml -p $(ANSIBLE_DIR)/roles
	ansible-galaxy collection install -r requirements.yml

deploy:
	$(ANSIBLE_PLAYBOOK) playbooks/site.yml $(VAULT_OPT) -e image_tag=$(IMAGE_TAG)

deploy-storage:
	$(ANSIBLE_PLAYBOOK) playbooks/storage.yml $(VAULT_OPT)

deploy-app:
	$(ANSIBLE_PLAYBOOK) playbooks/app.yml $(VAULT_OPT) -e image_tag=$(IMAGE_TAG)

deploy-monitoring:
	$(ANSIBLE_PLAYBOOK) playbooks/monitoring.yml $(VAULT_OPT)

update:
	$(ANSIBLE_PLAYBOOK) playbooks/update.yml $(VAULT_OPT) -e image_tag=$(IMAGE_TAG)

rollback:
	@test "$(IMAGE_TAG)" != "latest" || (echo "Usage: make rollback IMAGE_TAG=<previous-stable-tag>"; exit 1)
	$(ANSIBLE_PLAYBOOK) playbooks/update.yml $(VAULT_OPT) -e image_tag=$(IMAGE_TAG)

promtool:
	docker run --rm --entrypoint promtool -v "$(CURDIR)/ansible/roles/monitoring/files:/rules:ro" $(PROM_IMAGE) check rules /rules/alerts.yml

promtool-config:
	cd $(ANSIBLE_DIR) && ansible monitoring $(VAULT_OPT) --become -m command -a "docker exec prometheus promtool check config /etc/prometheus/prometheus.yml"

gen-dashboards:
	python3 scripts/gen_dashboards.py
	python3 scripts/gen_status_page.py
	python3 scripts/gen_nginx_dashboard.py
	python3 scripts/gen_logs_dashboard.py

gen-alerts:
	python3 scripts/gen_alerts.py
	python3 scripts/gen_log_alerts.py

dashboards:
	$(ANSIBLE_PLAYBOOK) playbooks/monitoring.yml $(VAULT_OPT) --tags dashboards

e2e-logs:
	./scripts/e2e_logs.sh

lint:
	ANSIBLE_ROLES_PATH=$(CURDIR)/ansible/roles ansible-lint
	python3 -m py_compile scripts/*.py
	bash -n scripts/*.sh

test-generated:
	@before=$$(find ansible/roles/monitoring/files -type f | sort | xargs sha256sum); \
	$(MAKE) -s gen-dashboards gen-alerts > /dev/null; \
	after=$$(find ansible/roles/monitoring/files -type f | sort | xargs sha256sum); \
	if [ "$$before" = "$$after" ]; then echo "OK: сгенерированные файлы актуальны"; else echo "FAIL: сгенерированные файлы были устаревшими, закоммитьте изменения"; exit 1; fi

test: lint test-generated promtool
	$(ANSIBLE_PLAYBOOK) playbooks/site.yml $(VAULT_OPT) --syntax-check
	cd $(ANSIBLE_DIR) && ansible all $(VAULT_OPT) -m ping

smoke:
	./scripts/smoke.sh

.PHONY: bootstrap deploy deploy-storage deploy-app deploy-monitoring update rollback promtool promtool-config gen-dashboards gen-alerts dashboards e2e-logs lint test-generated test smoke
