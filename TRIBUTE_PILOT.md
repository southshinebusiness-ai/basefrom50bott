# Tribute pilot — BASEFROM50

**Branch is not deployed. Production main remains unchanged.**

## Test setup

1. Create a separate private test channel. Never add Tribute to the real ULTIMATE GUIDE before the pilot.
2. Open verified @Tribute, finish creator verification, connect the **test channel** and grant Tribute invite/admin rights.
3. Create a **one-time** channel subscription, no recurring charges, in RUB. Set 100 RUB only if the Tribute UI permits it.
4. Copy the official Telegram subscription URL via Creator Dashboard → Channels & Groups → Subscription → Links.
5. Publish the actual offer and copy its HTTPS URL.
6. Deploy this branch to a **separate test bot**, using its own BOT_TOKEN, PRIVATE_CHANNEL_ID and DB_PATH.

## Test environment

TRIBUTE_PAYMENT_URL=<actual Tribute subscription URL>
OFFER_URL=<published HTTPS offer URL>
PRICE_ULTIMATE_GUIDE=100
PRIVATE_CHANNEL_ID=<test channel numeric ID>
DB_PATH=data/test-bot.db

Review the other environment settings. Do not reuse the production database or channel ID.

## Expected flow

- The ULTIMATE GUIDE screen includes a clickable offer hyperlink before the purchase button when OFFER_URL is configured.
- Clicking the buy button opens a short confirmation screen with a link to the Tribute checkout.
- The bot does not create a YooMoney invoice in Tribute mode.
- The test bot does not reject join requests when Tribute manages access.
- Tribute grants access to the test channel. The existing bot's payment statistics are **not** updated by Tribute in this pilot.

## Acceptance checks

- Price displayed in the test bot equals the price on Tribute.
- Offer hyperlink opens the published document.
- The buyer pays via **direct SBP**. If the flow instead requires buying Telegram Stars, do not roll out.
- Payment is successful and access is automatically granted.
- No recurring billing; access remains after reopening Telegram.
- No effect on existing BASEFROM50 users, channel, or payments.

Do not merge or deploy this branch to production before a successful test and explicit review of production channel membership, analytics, and purchase recovery.
