import json
from datetime import datetime, timedelta
from typing import Literal

from django.utils import timezone
from pydantic import BaseModel, Field
from enum import Enum
from decimal import Decimal

from core.ld import format_ld_date


class BasePostDataType(BaseModel):
    pass


class QuestionOption(BaseModel):
    name: str
    type: Literal["Note"] = "Note"
    votes: int = 0

    def __init__(self, **data) -> None:
        data["votes"] = data.get("votes", data.get("replies", {}).get("totalItems", 0))

        super().__init__(**data)


class QuestionData(BasePostDataType):
    type: Literal["Question"]
    mode: Literal["oneOf", "anyOf"] | None = None
    options: list[QuestionOption] | None
    voter_count: int = Field(alias="http://joinmastodon.org/ns#votersCount", default=0)
    end_time: datetime | None = Field(alias="endTime")

    class Config:
        extra = "ignore"
        allow_population_by_field_name = True

    def __init__(self, **data) -> None:
        data["voter_count"] = data.get(
            "voter_count", data.get("votersCount", data.get("toot:votersCount", 0))
        )

        if "mode" not in data:
            data["mode"] = "anyOf" if "anyOf" in data else "oneOf"
        if "options" not in data:
            options = data.pop("anyOf", None)
            if not options:
                options = data.pop("oneOf", None)
            data["options"] = options
        super().__init__(**data)

    def to_mastodon_json(self, post, identity=None):
        from activities.models import PostInteraction

        multiple = self.mode == "anyOf"
        value = {
            "id": post.id,
            "expires_at": None,
            "expired": False,
            "multiple": multiple,
            "votes_count": 0,
            "voters_count": self.voter_count,
            "voted": False,
            "own_votes": [],
            "options": [],
            "emojis": [],
        }

        if self.end_time:
            value["expires_at"] = format_ld_date(self.end_time)
            value["expired"] = timezone.now() >= self.end_time

        options = self.options or []
        option_map = {}
        for index, option in enumerate(options):
            value["options"].append(
                {
                    "title": option.name,
                    "votes_count": option.votes,
                }
            )
            value["votes_count"] += option.votes
            option_map[option.name] = index

        if identity:
            votes = post.interactions.filter(
                identity=identity,
                type=PostInteraction.Types.vote,
            )
            value["voted"] = post.author == identity or votes.exists()
            value["own_votes"] = [
                option_map[vote.value] for vote in votes if vote.value in option_map
            ]

        return value


class ArticleData(BasePostDataType):
    type: Literal["Article"]
    attributed_to: str | None = Field(...)

    class Config:
        extra = "ignore"


# TRADING

class ProductData(BasePostDataType):
    type: Literal["Product"]
    productID: str
    name: str
    category: str


class DayOfWeek(Enum):
    Friday = "https://schema.org/Friday"
    Monday = "https://schema.org/Monday"
    PublicHolidays = "https://schema.org/PublicHolidays"
    Saturday = "https://schema.org/Saturday"
    Sunday = "https://schema.org/Sunday"
    Thursday = "https://schema.org/Thursday"
    Tuesday = "https://schema.org/Tuesday"
    Wednesday = "https://schema.org/Wednesday"


class OpeningHoursSpecification(BaseModel):
    closes: str | None
    daysOfWeek: DayOfWeek
    opens: str | None


class ServiceData(BasePostDataType):
    type: Literal["Service"]
    name: str | None
    hoursAvailable: OpeningHoursSpecification | None
    termsOfService: str | None
    provider: str
    category: str
    name: str


class PaymentMethod(Enum):
    """PaymentMethod enumeration based on schema.org/PaymentMethod
    """
    ByBankTransferInAdvance = "http://purl.org/goodrelations/v1#ByBankTransferInAdvance"
    ByInvoice = "http://purl.org/goodrelations/v1#ByInvoice"
    Cash = "http://purl.org/goodrelations/v1#Cash"
    CheckInAdvance = "http://purl.org/goodrelations/v1#CheckInAdvance"
    COD = "http://purl.org/goodrelations/v1#COD"
    DirectDebit = "http://purl.org/goodrelations/v1#DirectDebit"
    GoogleCheckout = "http://purl.org/goodrelations/v1#GoogleCheckout"
    PayPal = "http://purl.org/goodrelations/v1#PayPal"
    PaySwarm = "http://purl.org/goodrelations/v1#PaySwarm"


class ItemAvailability(Enum):
    """ItemAvailability accoding to schema.org/ItemAvailability
    """
    BackOrder = "https://schema.org/BackOrder"
    Discontinued = "https://schema.org/Discontinued"
    InStock = "https://schema.org/InStock"
    InStoreOnly = "https://schema.org/InStoreOnly"
    LimitedAvailability = "https://schema.org/LimitedAvailability"
    OnlineOnly = "https://schema.org/OnlineOnly"
    OutOfStock = "https://schema.org/OutOfStock"
    PreOrder = "https://schema.org/PreOrder"
    PreSale = "https://schema.org/PreSale"
    SoldOut = "https://schema.org/SoldOut"


class WarrantyPromise(BaseModel):
    """Based on schema.org/WarrantyPromise
    """
    durationOfWarranty: timedelta

class OfferData(BasePostDataType):
    type: Literal["Offer"]
    acceptedPaymentMethod: PaymentMethod
    availability: ItemAvailability | None
    availabilityStarts: datetime | None
    availabilityEnds: datetime | None

    deliveryLeadTime: timedelta | None

    itemOffered:  str # ID of the Product or Service offered
    offeredBy: str # ID of the identity offering

    price: Decimal
    priceCurrency: str # Follow ISO 4217, where applicable.
    priceValidUntil : datetime | None

    warranty: WarrantyPromise | None # ID of the WarrantyPromise object


class PaymentStatusType(Enum):
    PaymentAutomaticallyApplied = "https://schema.org/PaymentAutomaticallyApplied"
    PaymentComplete = "https://schema.org/PaymentComplete"
    PaymentDeclined = "https://schema.org/PaymentDeclined"
    PaymentDue = "https://schema.org/PaymentDue"
    PaymentPastDue = "https://schema.org/PaymentPastDue"


class MonetaryAmount(BaseModel):
    """Subset of schema.org/MonetaryAmount
    """
    currency: str
    value: Decimal


class InvoiceData(BasePostDataType):
    """Subset of attributes from schema.org/Invoice
    """
    type: Literal["Invoice"]

    accountId: str # ID of the Person invoiced
    customer: str # ID of the Person receiving the Product/Service
    provider: str # ID of the seller

    billingPeriod: str | None
    confirmationNumber: str | None

    paymentMethod: PaymentMethod
    paymentDueDate: datetime | None
    paymentStatus: PaymentStatusType
    totalPaymentDue: MonetaryAmount
    scheduledPaymentDate: datetime | None


PostDataType = QuestionData | ArticleData | ProductData | ServiceData | OfferData | InvoiceData


class PostTypeData(BaseModel):
    __root__: PostDataType = Field(discriminator="type")


class PostTypeDataEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, BasePostDataType):
            return obj.dict()
        elif isinstance(obj, datetime):
            return obj.isoformat()
        return json.JSONEncoder.default(self, obj)


class PostTypeDataDecoder(json.JSONDecoder):
    def decode(self, *args, **kwargs):
        s = super().decode(*args, **kwargs)
        if isinstance(s, dict):
            return PostTypeData.parse_obj(s).__root__
        return s
