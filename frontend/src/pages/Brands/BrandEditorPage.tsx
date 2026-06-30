/**
 * BrandEditorPage — editor de una marca (ruta /brands/:brandId/edit).
 *
 * Carga la marca por id, permite editar nombre, logo_text y los 5 colores
 * de la paleta (Fondo, Texto, Primario, Acento, Acento 2), y guarda con
 * brandsApi.update(). Al guardar, vuelve a /brands.
 *
 * a11y:
 *  - Cada control tiene label visible.
 *  - Errores en aria-live (region assertive para errores, polite para éxito).
 *  - Foco automático al primer campo al cargar.
 *  - Navegación completa por teclado (Tab / Shift+Tab / Enter).
 *  - Botones con minHeight 44px (vía componente Button).
 */
import { type FormEvent, useEffect, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { brands as brandsApi, type Brand, ApiError } from '../../api/client';
import { Button, ColorPicker } from '../../components';
import { es } from '../../i18n/es';

const PALETTE_KEYS = ['fondo', 'texto', 'primario', 'acento', 'acento2'] as const;
type PaletteKey = (typeof PALETTE_KEYS)[number];

type Palette = Record<PaletteKey, string>;

const PALETTE_DEFAULTS: Palette = {
  fondo: '#FFFFFF',
  texto: '#0E1B1A',
  primario: '#1F8276',
  acento: '#E0A85E',
  acento2: '#B07A2A',
};

function isHexColor(value: unknown): value is string {
  return typeof value === 'string' && /^#[0-9A-Fa-f]{6}$/.test(value);
}

function readPalette(brand: Brand): Palette {
  const source = (brand.palette ?? {}) as Record<string, unknown>;
  return {
    fondo: isHexColor(source.fondo) ? source.fondo.toUpperCase() : PALETTE_DEFAULTS.fondo,
    texto: isHexColor(source.texto) ? source.texto.toUpperCase() : PALETTE_DEFAULTS.texto,
    primario: isHexColor(source.primario) ? source.primario.toUpperCase() : PALETTE_DEFAULTS.primario,
    acento: isHexColor(source.acento) ? source.acento.toUpperCase() : PALETTE_DEFAULTS.acento,
    acento2: isHexColor(source.acento2) ? source.acento2.toUpperCase() : PALETTE_DEFAULTS.acento2,
  };
}

function labelFor(key: PaletteKey): string {
  return es.palette_keys[key];
}

export function BrandEditorPage() {
  const { brandId } = useParams<{ brandId: string }>();
  const navigate = useNavigate();

  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');

  const [name, setName] = useState('');
  const [logoText, setLogoText] = useState('');
  const [palette, setPalette] = useState<Palette | null>(null);

  const [nameError, setNameError] = useState('');
  const [paletteErrors, setPaletteErrors] = useState<Partial<Record<PaletteKey, string>>>({});

  const [busy, setBusy] = useState(false);
  const [submitError, setSubmitError] = useState('');
  const [success, setSuccess] = useState('');

  const firstFieldRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!brandId) {
      setLoadError('Identificador de marca inválido.');
      setLoading(false);
      return;
    }
    let cancelled = false;
    brandsApi
      .get(Number(brandId))
      .then((brand) => {
        if (cancelled) return;
        setName(brand.name ?? '');
        setLogoText(brand.logo_text ?? '');
        setPalette(readPalette(brand));
      })
      .catch((err) => {
        if (cancelled) return;
        setLoadError(
          err instanceof ApiError ? err.detail : es.brand_editor.load_error,
        );
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [brandId]);

  useEffect(() => {
    if (!loading && !loadError && firstFieldRef.current) {
      firstFieldRef.current.focus();
    }
  }, [loading, loadError]);

  function updatePalette(key: PaletteKey, value: string) {
    setPalette((prev) => (prev ? { ...prev, [key]: value } : prev));
    if (paletteErrors[key]) {
      setPaletteErrors((prev) => ({ ...prev, [key]: undefined }));
    }
  }

  function validate(): boolean {
    let ok = true;
    if (!name.trim()) {
      setNameError('Escribí un nombre para tu marca.');
      ok = false;
    } else {
      setNameError('');
    }
    if (palette) {
      const newErrors: Partial<Record<PaletteKey, string>> = {};
      for (const k of PALETTE_KEYS) {
        if (!/^#[0-9A-Fa-f]{6}$/.test(palette[k])) {
          newErrors[k] = 'Tiene que ser un hexadecimal válido (#RRGGBB).';
          ok = false;
        }
      }
      setPaletteErrors(newErrors);
    } else {
      ok = false;
    }
    return ok;
  }

  async function loadBrand() {
    if (!brandId) return;
    setLoading(true);
    setLoadError('');
    try {
      const brand = await brandsApi.get(Number(brandId));
      setName(brand.name ?? '');
      setLogoText(brand.logo_text ?? '');
      setPalette(readPalette(brand));
    } catch (err) {
      setLoadError(
        err instanceof ApiError ? err.detail : es.brand_editor.load_error,
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitError('');
    setSuccess('');
    if (!validate() || !palette || !brandId) return;

    setBusy(true);
    try {
      await brandsApi.update(Number(brandId), {
        name: name.trim(),
        logo_text: logoText.trim() || name.trim(),
        palette: { ...palette },
      });
      setSuccess(es.brand_editor.save_success);
      window.setTimeout(() => {
        navigate('/brands');
      }, 600);
    } catch (err) {
      setSubmitError(
        err instanceof ApiError
          ? err.detail
          : es.brand_editor.save_error_generic,
      );
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <section
        aria-busy="true"
        aria-live="polite"
        style={{
          padding: 'var(--space-10) 0',
          color: 'var(--slate-500)',
        }}
      >
        Cargando la marca…
      </section>
    );
  }

  if (loadError || !palette) {
    return (
      <section style={{ display: 'grid', gap: 'var(--space-5)', maxWidth: 560 }}>
        <h1
          style={{
            margin: 0,
            fontFamily: 'var(--font-display)',
            fontSize: 'var(--font-size-2xl)',
            color: 'var(--error)',
          }}
        >
          No pudimos cargar la marca
        </h1>
        <p
          role="alert"
          aria-live="assertive"
          aria-atomic="true"
          style={{
            margin: 0,
            color: 'var(--error)',
            background: 'var(--error-bg)',
            padding: 'var(--space-3) var(--space-4)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--error)',
            fontSize: 'var(--font-size-sm)',
          }}
        >
          {loadError || es.brand_editor.load_error}
        </p>
        <div style={{ display: 'flex', gap: 'var(--space-3)', flexWrap: 'wrap' }}>
          <Button variant="primary" onClick={() => void loadBrand()}>
            Reintentar
          </Button>
          <Link to="/brands" style={{ textDecoration: 'none' }}>
            <Button variant="secondary">{es.brand_editor.back}</Button>
          </Link>
        </div>
      </section>
    );
  }

  return (
    <section>
      <div
        style={{
          display: 'flex',
          alignItems: 'flex-end',
          justifyContent: 'space-between',
          gap: 'var(--space-4)',
          flexWrap: 'wrap',
          marginBottom: 'var(--space-6)',
        }}
      >
        <div>
          <h1
            style={{
              margin: '0 0 var(--space-1)',
              fontFamily: 'var(--font-display)',
              fontSize: 'var(--font-size-2xl)',
              color: 'var(--ink)',
            }}
          >
            {es.brand_editor.title}
          </h1>
          <p
            style={{
              margin: 0,
              fontSize: 'var(--font-size-sm)',
              color: 'var(--slate-500)',
            }}
          >
            {es.brand_editor.subtitle}
          </p>
        </div>
        <Link to="/brands" style={{ textDecoration: 'none' }}>
          <Button variant="ghost" size="sm">
            ← {es.brand_editor.back}
          </Button>
        </Link>
      </div>

      <form
        onSubmit={handleSubmit}
        noValidate
        aria-label={es.brand_editor.title}
        style={{
          background: 'var(--white)',
          border: '1px solid var(--line)',
          borderRadius: 'var(--radius-lg)',
          padding: 'var(--space-6) var(--space-8)',
          boxShadow: 'var(--shadow-sm)',
          display: 'grid',
          gap: 'var(--space-8)',
        }}
      >
        <fieldset
          style={{
            border: 'none',
            padding: 0,
            margin: 0,
            display: 'grid',
            gap: 'var(--space-5)',
          }}
        >
          <legend
            style={{
              fontFamily: 'var(--font-display)',
              fontSize: 'var(--font-size-lg)',
              fontWeight: 700,
              color: 'var(--ink)',
              padding: 0,
              marginBottom: 'var(--space-2)',
            }}
          >
            {es.brand_editor.section_name}
          </legend>

          <div style={{ display: 'grid', gap: 'var(--space-1)' }}>
            <label
              htmlFor="brand-name"
              style={{
                display: 'block',
                fontSize: 'var(--font-size-sm)',
                fontWeight: 600,
                color: 'var(--ink)',
              }}
            >
              {es.brand_editor.name_label}
            </label>
            <input
              ref={firstFieldRef}
              id="brand-name"
              type="text"
              required
              minLength={1}
              maxLength={120}
              value={name}
              onChange={(e) => {
                setName(e.target.value);
                if (nameError) setNameError('');
              }}
              aria-invalid={nameError ? 'true' : undefined}
              aria-describedby={
                nameError ? 'brand-name-error' : 'brand-name-hint'
              }
              style={inputStyle}
            />
            {nameError ? (
              <p
                id="brand-name-error"
                role="alert"
                style={errorTextStyle}
              >
                {nameError}
              </p>
            ) : (
              <p id="brand-name-hint" style={hintTextStyle}>
                {es.brand_editor.name_hint}
              </p>
            )}
          </div>

          <div style={{ display: 'grid', gap: 'var(--space-1)' }}>
            <label
              htmlFor="brand-logo-text"
              style={{
                display: 'block',
                fontSize: 'var(--font-size-sm)',
                fontWeight: 600,
                color: 'var(--ink)',
              }}
            >
              {es.brand_editor.logo_text_label}{' '}
              <span
                style={{ color: 'var(--slate-500)', fontWeight: 400 }}
              >
                (opcional)
              </span>
            </label>
            <input
              id="brand-logo-text"
              type="text"
              maxLength={120}
              value={logoText}
              onChange={(e) => setLogoText(e.target.value)}
              aria-describedby="brand-logo-hint"
              style={inputStyle}
            />
            <p id="brand-logo-hint" style={hintTextStyle}>
              {es.brand_editor.logo_text_hint}
            </p>
          </div>
        </fieldset>

        <fieldset
          aria-describedby="palette-hint"
          style={{
            border: 'none',
            padding: 0,
            margin: 0,
            display: 'grid',
            gap: 'var(--space-5)',
          }}
        >
          <legend
            style={{
              fontFamily: 'var(--font-display)',
              fontSize: 'var(--font-size-lg)',
              fontWeight: 700,
              color: 'var(--ink)',
              padding: 0,
              marginBottom: 'var(--space-1)',
            }}
          >
            {es.brand_editor.section_palette}
          </legend>
          <p
            id="palette-hint"
            style={{
              ...hintTextStyle,
              maxWidth: '60ch',
              marginBottom: 'var(--space-1)',
            }}
          >
            {es.brand_editor.palette_hint}
          </p>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
              gap: 'var(--space-5)',
            }}
          >
            {PALETTE_KEYS.map((key) => (
              <ColorPicker
                key={key}
                id={`palette-${key}`}
                label={labelFor(key)}
                value={palette[key]}
                onChange={(v) => updatePalette(key, v)}
                error={paletteErrors[key]}
              />
            ))}
          </div>
        </fieldset>

        <div aria-live="assertive" aria-atomic="true">
          {submitError && (
            <p role="alert" style={errorBannerStyle}>
              {submitError}
            </p>
          )}
          {success && (
            <p role="status" style={successBannerStyle}>
              {success}
            </p>
          )}
        </div>

        <div
          style={{
            display: 'flex',
            gap: 'var(--space-3)',
            flexWrap: 'wrap',
            justifyContent: 'flex-end',
            borderTop: '1px solid var(--line)',
            paddingTop: 'var(--space-5)',
          }}
        >
          <Link to="/brands" style={{ textDecoration: 'none' }}>
            <Button variant="secondary" disabled={busy}>
              {es.brand_editor.cancel}
            </Button>
          </Link>
          <Button type="submit" variant="primary" busy={busy}>
            {busy ? es.brand_editor.saving : es.brand_editor.save}
          </Button>
        </div>
      </form>
    </section>
  );
}

const inputStyle: React.CSSProperties = {
  display: 'block',
  width: '100%',
  minHeight: 44,
  padding: 'var(--space-2) var(--space-3)',
  border: '1.5px solid var(--line)',
  borderRadius: 'var(--radius-md)',
  fontSize: 'var(--font-size-base)',
  color: 'var(--ink)',
  background: 'var(--paper)',
  boxSizing: 'border-box',
  fontFamily: 'var(--font-body)',
  outline: 'none',
  transition:
    'border-color var(--transition-fast), box-shadow var(--transition-fast)',
};

const errorTextStyle: React.CSSProperties = {
  margin: 0,
  fontSize: 'var(--font-size-xs)',
  color: 'var(--error)',
  fontWeight: 500,
};

const hintTextStyle: React.CSSProperties = {
  margin: 0,
  fontSize: 'var(--font-size-xs)',
  color: 'var(--slate-500)',
};

const errorBannerStyle: React.CSSProperties = {
  margin: 0,
  color: 'var(--error)',
  background: 'var(--error-bg)',
  padding: 'var(--space-3) var(--space-4)',
  borderRadius: 'var(--radius-md)',
  border: '1px solid var(--error)',
  fontSize: 'var(--font-size-sm)',
  display: 'flex',
  alignItems: 'center',
  gap: 'var(--space-2)',
};

const successBannerStyle: React.CSSProperties = {
  margin: 0,
  color: '#1a7a4a',
  background: '#e6f9f0',
  padding: 'var(--space-3) var(--space-4)',
  borderRadius: 'var(--radius-md)',
  border: '1px solid #a7e0c4',
  fontSize: 'var(--font-size-sm)',
  display: 'flex',
  alignItems: 'center',
  gap: 'var(--space-2)',
};
