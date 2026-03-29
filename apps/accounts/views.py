from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.contrib import messages

from apps.accounts.forms import (
    UserSettingsForm,
    BrandProfileForm,
    OnboardingStep1Form,
    OnboardingStep2Form,
    OnboardingStep3Form,
)


@login_required
def settings_view(request):
    """User settings page with two forms: account info + brand profile."""
    if request.method == "POST":
        user_form = UserSettingsForm(request.POST, request.FILES, instance=request.user)
        brand_form = BrandProfileForm(request.POST, instance=request.user.profile)
        if user_form.is_valid() and brand_form.is_valid():
            user_form.save()
            brand_form.save()
            messages.success(request, "Settings saved.")
            return redirect("accounts:settings")
    else:
        user_form = UserSettingsForm(instance=request.user)
        brand_form = BrandProfileForm(instance=request.user.profile)

    return render(request, "accounts/settings.html", {
        "user_form": user_form,
        "brand_form": brand_form,
        "page_title": "Settings",
    })


@login_required
def onboarding_view(request):
    """Multi-step onboarding wizard."""
    profile = request.user.profile
    step = int(request.GET.get("step", 1))

    if step == 1:
        form_class = OnboardingStep1Form
    elif step == 2:
        form_class = OnboardingStep2Form
    elif step == 3:
        form_class = OnboardingStep3Form
    else:
        return redirect("accounts:onboarding")

    if request.method == "POST":
        form = form_class(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            if step < 3:
                return redirect(f"/accounts/onboarding/?step={step + 1}")
            else:
                # Final step — mark onboarding as complete
                request.user.onboarding_completed = True
                request.user.save(update_fields=["onboarding_completed"])
                messages.success(request, "Welcome to Kova Agent! Your agents are ready.")
                return redirect("brief:home")
    else:
        form = form_class(instance=profile)

    return render(request, "accounts/onboarding.html", {
        "form": form,
        "step": step,
        "total_steps": 3,
        "page_title": "Setup Your Brand",
    })
