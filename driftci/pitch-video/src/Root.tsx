import { Composition } from "remotion";
import { DriftCI, TOTAL } from "./DriftCI";

export const Root = () => (
  <Composition
    id="DriftCI"
    component={DriftCI}
    durationInFrames={TOTAL}
    fps={30}
    width={1920}
    height={1080}
  />
);
