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

.PHONY: bootstrap deploy update rollback
