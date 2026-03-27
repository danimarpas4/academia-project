class ReferralMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        ref_code = request.GET.get('ref')
        if ref_code:
            request.session['referral_code'] = ref_code

        response = self.get_response(request)
        return response
