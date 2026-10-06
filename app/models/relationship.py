from enum import Enum


class FamilyRelationship(str, Enum):
    """Single source of truth for supported family relationships."""
    HUSBAND = "husband"
    WIFE = "wife"
    FATHER = "father"
    MOTHER = "mother"
    SON = "son"
    DAUGHTER = "daughter"
    BROTHER = "brother"
    SISTER = "sister"
    GRANDFATHER = "grandfather"
    GRANDMOTHER = "grandmother"
    GRANDSON = "grandson"
    GRANDDAUGHTER = "granddaughter"
    UNCLE = "uncle"
    AUNT = "aunt"
    COUSIN = "cousin"
    OTHER = "other"

    @property
    def label(self) -> str:
        """User-friendly title-cased display label."""
        labels = {
            FamilyRelationship.HUSBAND: "Husband",
            FamilyRelationship.WIFE: "Wife",
            FamilyRelationship.FATHER: "Father",
            FamilyRelationship.MOTHER: "Mother",
            FamilyRelationship.SON: "Son",
            FamilyRelationship.DAUGHTER: "Daughter",
            FamilyRelationship.BROTHER: "Brother",
            FamilyRelationship.SISTER: "Sister",
            FamilyRelationship.GRANDFATHER: "Grandfather",
            FamilyRelationship.GRANDMOTHER: "Grandmother",
            FamilyRelationship.GRANDSON: "Grandson",
            FamilyRelationship.GRANDDAUGHTER: "Granddaughter",
            FamilyRelationship.UNCLE: "Uncle",
            FamilyRelationship.AUNT: "Aunt",
            FamilyRelationship.COUSIN: "Cousin",
            FamilyRelationship.OTHER: "Other",
        }
        return labels.get(self, self.value.replace("_", " ").title())

    @classmethod
    def get_relationship_label(cls, value: str | None) -> str:
        if not value:
            return "Other"
        try:
            return cls(value.lower()).label
        except ValueError:
            return value.replace("_", " ").title()
