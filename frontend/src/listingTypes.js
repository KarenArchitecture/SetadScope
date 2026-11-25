import { Building2, FileText, Gavel } from "lucide-react";
import Dashboard, { DetailModal } from "./pages/Dashboard";
import { getAuctionById, getTenderById } from "./services/api";

export const listingTypes = [
  {
    key: "auction", page: "auctions", path: "/auctions", title: "مزایده‌ها",
    label: "مزایده", icon: Gavel, badgeIcon: Gavel, Page: Dashboard,
    Details: DetailModal, getDetails: getAuctionById, showCollection: true,
    excludedFilters: ["type_name", "documents_deadline_from", "documents_deadline_to"],
  },
  {
    key: "tender", page: "tenders", path: "/tenders", title: "مناقصه‌ها",
    label: "مناقصه", icon: FileText, badgeIcon: Building2, Page: Dashboard,
    Details: DetailModal, getDetails: getTenderById, showCollection: false,
    showDocumentsDeadline: true, excludedFilters: ["collection_group", "price_min", "price_max"],
  },
];

export const defaultListing = listingTypes[0];
export const listingByKey = Object.fromEntries(listingTypes.map((listing) => [listing.key, listing]));
