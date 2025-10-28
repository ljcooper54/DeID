import uuid
from .models import EntityCategory
from .persistence import Persistence

class PseudonymMapper:
    def __init__(self, persistence: Persistence):
        self.db = persistence

    def _cat_prefix(self, category: EntityCategory) -> str:
        return {
            EntityCategory.PERSON: "Person",
            EntityCategory.ORG: "Org",
            EntityCategory.LOCATION: "Location",
            EntityCategory.PATENT: "Patent",
            EntityCategory.PRODUCT_CODE: "ProductCode",
            EntityCategory.OTHER: "Other",
        }[category]

    def get_or_create_pseudonym(
        self,
        project_id: int,
        category: EntityCategory,
        original_value: str
    ) -> str:
        # Check existing
        row = self.db.get_mapping(project_id, original_value)
        if row:
            return row["pseudonym"]

        # Create new
        last_idx = self.db.get_last_index(project_id, category)
        new_idx = last_idx + 1
        pseudonym = f"{self._cat_prefix(category)}_{new_idx:03d}"

        entity_id = str(uuid.uuid4())
        self.db.insert_mapping(
            entity_id,
            project_id,
            category,
            original_value,
            pseudonym
        )
        self.db.set_last_index(project_id, category, new_idx)
        return pseudonym
