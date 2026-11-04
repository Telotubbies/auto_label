// Typed API client, split per feature under `api/`. This module is the stable import surface:
// `import { api, fileUrl, get, post } from '@/lib/api'` keeps working.
import { P } from './api/client'
import { coreApi } from './api/core'
import { datasetApi } from './api/dataset'
import { modelApi } from './api/models'
import { insightsApi, studioApi } from './api/insights'
import { governanceApi } from './api/governance'
import { qaApi } from './api/qa'
import { streamsApi } from './api/streams'

export {
  API_ORIGIN, ApiError, del, download, fileUrl, get, patch, post, put, req, tokens, upload,
} from './api/client'

export const api = {
  ...coreApi,
  ...datasetApi,
  ...modelApi,
  insights: insightsApi,
  ...studioApi,
  ...governanceApi,
  ...qaApi,
  ...streamsApi,
  P,
}
