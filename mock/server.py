import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from seeds.providers import (
    hubspot, stripe, customerio,
    meta, google_ads, google_analytics, google_sheets, calendly, smartlook,
    salesforce, linkedin, pinterest, snapchat, twitter,
    mailchimp, klaviyo, activecampaign, sendgrid, twilio, shopify,
    woocommerce, mixpanel, amplitude, segment, intercom, zendesk,
    zoom, meta_ad_library, google_ads_transparency,
    serp, ai_answers, competitor_pages, social_scrape,
)

app = FastAPI(title="OS Mock Providers")

routers = {
    "/hubspot": hubspot,
    "/stripe": stripe,
    "/customerio": customerio,
    "/meta": meta,
    "/google-ads": google_ads,
    "/ga4/v1beta": google_analytics,
    "/sheets/v4": google_sheets,
    "/calendly": calendly,
    "/smartlook": smartlook,
    "/salesforce/services/data/v67.0": salesforce,
    "/linkedin/rest": linkedin,
    "/pinterest/v5": pinterest,
    "/snapchat": snapchat,
    "/twitter": twitter,
    "/mailchimp": mailchimp,
    "/klaviyo": klaviyo,
    "/activecampaign": activecampaign,
    "/sendgrid": sendgrid,
    "/twilio": twilio,
    "/shopify": shopify,
    "/woocommerce/wc/v3": woocommerce,
    "/mixpanel": mixpanel,
    "/amplitude": amplitude,
    "/segment": segment,
    "/intercom": intercom,
    "/zendesk/api/v2": zendesk,
    "/zoom": zoom,
    "/meta-ad-library": meta_ad_library,
    "/serpapi": google_ads_transparency,
    "/serp": serp,
    "/answers": ai_answers,
    "/pages": competitor_pages,
    "/social-scrape": social_scrape,
}

for prefix, mod in routers.items():
    app.include_router(mod.router, prefix=prefix)


from seeds.providers.twitter import _TwAuthError


@app.exception_handler(_TwAuthError)
async def tw_auth_handler(request, exc):
    return JSONResponse(
        status_code=401,
        content={"title": "Unauthorized", "type": "about:blank", "status": 401, "detail": "Unauthorized"},
    )


@app.get("/health")
async def health():
    return {"status": "ok", "providers": list(routers.keys())}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8100)
