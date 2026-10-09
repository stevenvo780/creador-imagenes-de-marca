import { useEffect, useState } from "react";
import {
  isAbort,
  mediaError,
  privateImage,
  releasePrivateUrl,
} from "../../api/media";
export function PrivateImage({ path, alt }: { path: string; alt: string }) {
  const [image, setImage] = useState<{
    path: string;
    url: string;
  } | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const c = new AbortController();
    let url = "";
    setImage(null);
    setError("");
    void privateImage(path, c.signal)
      .then((value) => {
        url = value;
        if (c.signal.aborted) releasePrivateUrl(value);
        else setImage({ path, url: value });
      })
      .catch((e) => {
        if (!isAbort(e)) setError(mediaError(e));
      });
    return () => {
      c.abort();
      if (url) releasePrivateUrl(url);
    };
  }, [path]);
  if (error) return <p role="alert">{error}</p>;
  if (!image || image.path !== path)
    return (
      <div className="media-placeholder" role="status">
        Cargando imagen…
      </div>
    );
  return <img className="media-image" src={image.url} alt={alt} />;
}
