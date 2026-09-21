import { useState } from "react";
import { GaugeIcon, SlidersHorizontalIcon, WavesIcon } from "lucide-react";
import { AltitudeCard } from "./components/AltitudeCard";
import { AttitudeIndicator } from "./components/AttitudeIndicator";
import { BatteryBox } from "./components/BatteryBox";
import { ChartPanel } from "./components/ChartPanel";
import { FlightStatusCard } from "./components/FlightStatusCard";
import { LinkCard } from "./components/LinkCard";
import { NavSignalBox } from "./components/NavSignalBox";
import { SbcStatusCard } from "./components/SbcStatusCard";
import { TopBar } from "./components/TopBar";
import { gyroSeries, motorSeries, pidSeries, vehicle } from "./data/telemetry";
import { useTelemetry } from "./hooks/useTelemetry";
import type { Telemetry } from "./types/telemetry";

function activeWarning(t: Telemetry): string | null {
  if (t.source.status === "offline") return "esp json offline";
  if (t.source.status === "stale") return "nrf packets stale";
  if (t.battery.percent < 25) return "battery low · rtl advised";
  if (t.link.loss > 5) return "downlink packet loss";
  if (t.sbc.temp > 72) return "sbc thermal limit";
  if (t.nav.hdop > 1.2) return "gps hdop degraded";
  return null;
}

function sourceTone(status: Telemetry["source"]["status"]): string {
  if (status === "online") return "bg-sig-green";
  if (status === "stale") return "bg-sig-amber";
  return "bg-sig-red";
}

export function App({ streaming = true }: { streaming?: boolean }) {
  const [live, setLive] = useState(streaming);
  const t = useTelemetry(live);

  return (
    <div className="hud-grid-bg flex min-h-full w-full flex-col bg-hud-bg font-sans">
      <TopBar
        live={live}
        onToggleLive={() => setLive((value) => !value)}
        armed={t.flight.armed}
        mode={t.flight.mode}
        clock={t.clock}
        warning={activeWarning(t)}
      />

      <main className="flex flex-1 flex-col gap-2 p-2.5">
        {t.source.status !== "online" ? (
          <div
            className={`flex items-center justify-between gap-3 rounded border px-3 py-2 font-mono text-2xs uppercase tracking-[0.08em] ${
              t.source.status === "offline"
                ? "border-sig-red/50 bg-sig-red/10 text-sig-red"
                : "border-sig-amber/50 bg-sig-amber/10 text-sig-amber"
            }`}
          >
            <span className="min-w-0 truncate">{t.source.message}</span>
            <span className="hidden min-w-0 truncate text-right sm:block">{t.source.endpoint}</span>
          </div>
        ) : null}

        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-12">
          <BatteryBox battery={t.battery} className="min-h-[150px] xl:col-span-3 xl:h-[164px]" />
          <NavSignalBox nav={t.nav} className="min-h-[150px] xl:col-span-4 xl:h-[164px]" />
          <AltitudeCard altitude={t.altitude} className="min-h-[150px] xl:col-span-2 xl:h-[164px]" />
          <LinkCard link={t.link} className="min-h-[150px] xl:col-span-3 xl:h-[164px]" />
        </div>

        <div className="grid grid-cols-1 gap-2 lg:grid-cols-2 xl:grid-cols-12">
          <FlightStatusCard flight={t.flight} className="min-h-[178px] xl:col-span-4 xl:h-[178px]" />
          <SbcStatusCard sbc={t.sbc} className="min-h-[178px] xl:col-span-5 xl:h-[178px]" />
          <AttitudeIndicator attitude={t.attitude} className="min-h-[150px] lg:col-span-2 xl:col-span-3 xl:h-[178px]" />
        </div>

        <div className="grid grid-cols-1 gap-2 xl:grid-cols-2">
          <ChartPanel
            label="PID Response"
            icon={<SlidersHorizontalIcon size={12} />}
            series={pidSeries}
            data={t.pid as unknown as Array<Record<string, number>>}
            domain={[-10, 10]}
            ticks={[-10, -5, 0, 5, 10]}
            unit="°"
            className="h-[196px]"
            footer={
              <>
                <span>err · deg · 60 s window</span>
                <span>rate 50 hz</span>
              </>
            }
          />
          <ChartPanel
            label="Motor Power"
            icon={<GaugeIcon size={12} />}
            series={motorSeries}
            data={t.motors as unknown as Array<Record<string, number>>}
            domain={[40, 80]}
            ticks={[40, 50, 60, 70, 80]}
            unit="%"
            className="h-[196px]"
            footer={
              <>
                <span>throttle out · quad-x</span>
                <span>
                  avg{" "}
                  {(
                    ((t.motors[t.motors.length - 1]?.m1 ?? 0) +
                      (t.motors[t.motors.length - 1]?.m2 ?? 0) +
                      (t.motors[t.motors.length - 1]?.m3 ?? 0) +
                      (t.motors[t.motors.length - 1]?.m4 ?? 0)) /
                    4
                  ).toFixed(1)}
                  %
                </span>
              </>
            }
          />
        </div>

        <ChartPanel
          label="Gyroscope · 3-Axis"
          icon={<WavesIcon size={12} />}
          series={gyroSeries}
          data={t.gyro as unknown as Array<Record<string, number>>}
          domain={[-40, 40]}
          ticks={[-40, -20, 0, 20, 40]}
          unit=""
          className="h-[170px]"
          footer={
            <>
              <span>deg/s · imu1 · filtered</span>
              <span>{vehicle.firmware}</span>
            </>
          }
        />

        <footer className="flex items-center justify-between px-1 pb-1 font-mono text-2xs text-hud-faint">
          <span className="flex items-center gap-1.5">
            <span className={`h-1.5 w-1.5 rounded-full ${live ? sourceTone(t.source.status) : "bg-hud-edge"}`} aria-hidden="true" />
            {live ? `${t.source.status} · ${t.source.endpoint}` : "stream held · last frame retained"}
          </span>
          <span className="hidden sm:block">esp32 json only · no mock fallback · gcs build 0.9.6</span>
        </footer>
      </main>
    </div>
  );
}
