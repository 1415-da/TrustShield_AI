import { Architecture } from "@/components/landing/architecture";
import { Hero } from "@/components/landing/hero";
import { LandingNav } from "@/components/landing/nav";
import { DemoRequest, Faq, Features, Footer, HowItWorks, Metrics, Trust } from "@/components/landing/sections";

export default function LandingPage() {
  return (
    <>
      <LandingNav />
      <main id="main">
        <Hero />
        <Architecture />
        <Features />
        <HowItWorks />
        <Trust />
        <Metrics />
        <Faq />
        <DemoRequest />
      </main>
      <Footer />
    </>
  );
}
