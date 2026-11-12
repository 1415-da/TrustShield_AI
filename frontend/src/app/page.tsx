import { Architecture } from "@/components/landing/architecture";
import { Hero } from "@/components/landing/hero";
import { LandingNav, SiteFooter } from "@/components/landing/nav";
import { Faq, Features, GetStarted, HowItWorks, Integrate, LiveStats, Metrics, Trust } from "@/components/landing/sections";

export default function LandingPage() {
  return (
    <>
      <LandingNav />
      <main id="main">
        <Hero />
        <LiveStats />
        <Architecture />
        <Features />
        <HowItWorks />
        <Integrate />
        <Trust />
        <Metrics />
        <Faq />
        <GetStarted />
      </main>
      <SiteFooter />
    </>
  );
}
